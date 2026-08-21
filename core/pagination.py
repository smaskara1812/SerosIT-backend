from rest_framework.pagination import PageNumberPagination


class MastersPagination(PageNumberPagination):
    """Default list pagination. Callers that need the full option set for a
    dropdown (rather than a browsable page) can ask for more via
    ?page_size=, capped at max_page_size so a runaway request can't pull an
    entire large table in one response."""

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 1000
