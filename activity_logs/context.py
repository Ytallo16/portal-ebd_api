from contextvars import ContextVar


_current_request = ContextVar('activity_log_request', default=None)
_entity_event_count = ContextVar('activity_log_entity_event_count', default=0)


def begin_activity_context(request):
    request_token = _current_request.set(request)
    count_token = _entity_event_count.set(0)
    return request_token, count_token


def end_activity_context(tokens):
    request_token, count_token = tokens
    _current_request.reset(request_token)
    _entity_event_count.reset(count_token)


def get_activity_request():
    return _current_request.get()


def mark_entity_event():
    _entity_event_count.set(_entity_event_count.get() + 1)


def has_entity_events():
    return _entity_event_count.get() > 0

