from django.utils.deprecation import MiddlewareMixin
from django.contrib.messages import get_messages
from django.template.loader import render_to_string


class msgMiddleware(MiddlewareMixin):
    """
    Middleware that moves messages into the HX-Trigger header when request is made with HTMX
    """

    def process_response(self, request, response):

        # The HX-Request header indicates that the request was made with HTMX
        if "HX-Request" not in request.headers:
            return response

        # Ignore HTTP redirections because HTMX cannot read the body
        if 300 <= response.status_code < 400:
            return response

        # Ignore client-side redirection because HTMX drops OOB swaps
        if "HX-Redirect" in response.headers:
            return response

        # Extract the messages
        messages = get_messages(request)
        if not messages:
            return response

        print('message from ',   messages)

        response.write(
            render_to_string(
                template_name="partials/toast.html",
                context={"messages": messages},
                request=request,
            )
        )

        return response
