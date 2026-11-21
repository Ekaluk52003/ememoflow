from unittest import mock

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser
from .models import ApprovalWorkflow, Comment, Document
from .notification_models import Notification


class CommentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        mk = lambda n: CustomUser.objects.create_user(username=n, email=f'{n}@x.test', password='pw-Test-12345')
        cls.owner, cls.cc, cls.outsider = mk('owner'), mk('ccuser'), mk('outsider')
        wf = ApprovalWorkflow.objects.create(name='WF', created_by=cls.owner)
        cls.doc = Document.objects.create(title='Doc', submitted_by=cls.owner, workflow=wf)
        cls.doc.authorized_users.add(cls.cc)
        cls.ref = cls.doc.document_reference
        cls.url = reverse('document_approval:comments', args=[cls.ref])

    def setUp(self):
        p = mock.patch('document.notification_service.redis.Redis')
        p.start(); self.addCleanup(p.stop)

    def post(self, user, text, **extra):
        self.client.force_login(user)
        return self.client.post(self.url, {'text': text, **extra})

    def test_outsider_has_no_access(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, {'text': 'hi'}).status_code, 403)
        self.assertEqual(self.client.get(reverse('document_approval:mention_users', args=[self.ref])).status_code, 403)
        self.assertEqual(Comment.objects.count(), 0)

    def test_post_and_reply_to_reply_attaches_to_root(self):
        self.post(self.owner, 'root')
        root = Comment.objects.get()
        self.post(self.cc, 'r1', parent=root.pk)
        r1 = Comment.objects.get(text='r1')
        self.post(self.owner, 'r2', parent=r1.pk)
        self.assertEqual(Comment.objects.get(text='r2').parent_id, root.pk)

    def test_mention_notifies_only_users_with_access(self):
        self.post(self.owner, 'hey @ccuser and @outsider')
        c = Comment.objects.get()
        n = Notification.objects.get(user=self.cc)
        self.assertEqual((n.kind, n.url, n.preview), ('mention', f'/document/{self.ref}/#comment-{c.pk}', 'hey @ccuser and @outsider'))
        self.assertFalse(Notification.objects.filter(user=self.outsider).exists())
        self.assertEqual(list(c.mentioned_users.all()), [self.cc])

    def test_no_email_is_sent(self):
        self.post(self.owner, 'hey @ccuser')
        self.assertEqual(len(mail.outbox), 0)

    def test_reply_notifies_parent_author(self):
        self.post(self.cc, 'question')
        self.post(self.owner, 'answer', parent=Comment.objects.get().pk)
        n = Notification.objects.get(user=self.cc)
        self.assertEqual(n.kind, 'reply')

    def test_own_reply_and_html_are_safe(self):
        self.post(self.owner, '<script>x</script> @ccuser')
        html = self.post(self.owner, 'again').content.decode()
        self.assertNotIn('<script>x', html)
        self.assertIn('&lt;script&gt;', html)

    def test_mention_users_only_lists_people_with_access(self):
        self.client.force_login(self.owner)
        names = [u['username'] for u in self.client.get(reverse('document_approval:mention_users', args=[self.ref])).json()]
        self.assertIn('ccuser', names)
        self.assertNotIn('outsider', names)

    def test_only_author_can_soft_delete(self):
        self.post(self.owner, 'mine')
        c = Comment.objects.get()
        url = reverse('document_approval:delete_comment', args=[c.pk])
        self.client.force_login(self.cc)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(url).status_code, 200)
        c.refresh_from_db()
        self.assertTrue(c.is_deleted)


class NotificationPageTests(TestCase):
    def test_page_and_single_delete(self):
        u = CustomUser.objects.create_user(username='u', email='u@x.test', password='pw-Test-12345')
        o = CustomUser.objects.create_user(username='o', email='o@x.test', password='pw-Test-12345')
        wf = ApprovalWorkflow.objects.create(name='WF', created_by=u)
        d = Document.objects.create(title='D', submitted_by=u, workflow=wf)
        mk = lambda user: Notification.objects.create(user=user, message='m', document=d, workflow_name='WF', url='/x/', kind='mention', preview='p')
        mine, theirs = mk(u), mk(o)
        self.client.force_login(u)
        self.assertContains(self.client.get(reverse('document_approval:notification_list')), 'data-del')
        self.assertNotEqual(self.client.post(reverse('document_approval:delete_notification', args=[theirs.pk])).status_code, 200)  # existing view maps the 404 to 400
        self.client.post(reverse('document_approval:delete_notification', args=[mine.pk]))
        self.assertFalse(Notification.objects.filter(pk=mine.pk).exists())
        self.assertTrue(Notification.objects.filter(pk=theirs.pk).exists())
