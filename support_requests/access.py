ANALYST_PERMISSION = "support_requests.view_supportrequest"


def is_support_request_analyst(user):
    return user.is_authenticated and user.has_perm(ANALYST_PERMISSION)
