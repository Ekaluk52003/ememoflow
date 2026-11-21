import re
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Q
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from accounts.models import CustomUser
from .models import Comment
from .notification_service import send_approval_notification
from .utils import get_allowed_document


def _highlight(comment):
    """Escaped comment text with real (notified) @mentions wrapped in a coloured span."""
    html = escape(comment.text)
    for u in comment.mentioned_users.all():
        html = re.sub(
            r'(?<!\w)@' + re.escape(escape(u.username)) + r'(?![\w+-])',
            lambda m: '<span class="px-1 rounded bg-neon-violet/20 font-semibold text-neon-violet">%s</span>' % m.group(0),
            html)
    return mark_safe(html)


def _render(request, document):
    comments = list(document.comments.select_related('author').prefetch_related('mentioned_users'))
    top = []
    for c in comments:
        c.html = _highlight(c)
        c.reply_list = []
    by_id = {c.pk: c for c in comments}
    for c in comments:
        (by_id[c.parent_id].reply_list if c.parent_id in by_id else top).append(c)
    return render(request, 'partials/comments.html', {'document': document, 'comments': top, 'total': len(comments)})


def _notify(request, document, comment, parent=None):
    names = {n.rstrip('.') for n in re.findall(r'@([\w.+-]+)', comment.text)}
    users = CustomUser.objects.filter(username__in=names, is_active=True).exclude(pk=request.user.pk)
    # only notify people who can actually open the document
    users = [u for u in users if get_allowed_document(u, document.document_reference)]
    comment.mentioned_users.set(users)
    who = request.user.get_full_name() or request.user.username
    targets = [(u, 'mentioned you on', 'mention') for u in users]
    if parent and parent.author_id != request.user.pk and parent.author not in users \
            and get_allowed_document(parent.author, document.document_reference):
        targets.append((parent.author, 'replied to your comment on', 'reply'))
    for u, verb, kind in targets:
        send_approval_notification(document, u, message=f"{who} {verb} #{document.document_reference} - {document.title}",
                                   anchor=f"#comment-{comment.pk}", preview=" ".join(comment.text.split())[:120], kind=kind)


@login_required
@require_http_methods(["GET", "POST"])
def comments(request, reference_id):
    document = get_allowed_document(request.user, reference_id)
    if document is None:
        return HttpResponseForbidden()
    if request.method == 'POST':
        text = request.POST.get('text', '').strip()[:2000]
        if text:
            parent = Comment.objects.filter(pk=request.POST.get('parent') or 0, document=document).first()
            if parent and parent.parent_id:  # replying to a reply: attach to the thread root
                parent = parent.parent
            comment = Comment.objects.create(document=document, author=request.user, text=text, parent=parent)
            _notify(request, document, comment, parent)
    return _render(request, document)


@login_required
@require_POST
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id, author=request.user)
    document = get_allowed_document(request.user, comment.document.document_reference)
    if document is None:
        return HttpResponseForbidden()
    comment.is_deleted = True
    comment.save(update_fields=['is_deleted'])
    return _render(request, document)


def _can_view(user, document):
    # suggestions only: cached 60s because the access query is heavy; notifying re-checks uncached in _notify
    key = f'mention-ok:{document.pk}:{user.pk}'
    ok = cache.get(key)
    if ok is None:
        ok = get_allowed_document(user, document.document_reference) is not None
        cache.set(key, ok, 60)
    return ok


@login_required
def mention_users(request, reference_id):
    """Type-ahead for @mentions: only users who can open this document."""
    document = get_allowed_document(request.user, reference_id)
    if document is None:
        return HttpResponseForbidden()
    q = request.GET.get('q', '').strip()
    # shortcut: access is checked per user on a small candidate slice, fine for a few hundred users
    candidates = CustomUser.objects.filter(is_active=True).exclude(pk=request.user.pk).filter(
        Q(username__istartswith=q) | Q(first_name__istartswith=q) | Q(last_name__istartswith=q)
    ).order_by('username')[:30]
    out = []
    for u in candidates:
        if _can_view(u, document):
            out.append({'username': u.username, 'name': u.get_full_name() or u.username})
        if len(out) == 8:
            break
    return JsonResponse(out, safe=False)
