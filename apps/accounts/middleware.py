from django.shortcuts import redirect
from django.urls import reverse


class ApprovalGateMiddleware:
    """
    Blocks unapproved residents (is_approved=False) from accessing core views.
    Directs them to a dedicated 'Pending Verification' notice page until
    a Barangay Administrator reviews and approves their account.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Exempt admin and kapitan users from resident approval checks
            if request.user.role == 'resident' and not request.user.is_approved:
                exempt_paths = [
                    reverse('accounts:pending_approval'),
                    reverse('accounts:logout'),
                ]

                # Check path prefixes for static/media files
                path = request.path
                is_exempt = any(path.startswith(p) for p in exempt_paths) or path.startswith('/static/') or path.startswith('/media/')

                if not is_exempt:
                    return redirect('accounts:pending_approval')

            elif request.user.is_authenticated and request.user.is_approved:
                # If already approved resident or staff visits pending page, redirect to home/dashboard
                if request.path == reverse('accounts:pending_approval'):
                    return redirect('accounts:dashboard')

        response = self.get_response(request)
        return response
