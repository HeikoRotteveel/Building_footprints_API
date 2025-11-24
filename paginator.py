from urllib.parse import urlencode
from fastapi import Request

class Paginator:
    def __init__(self, request: Request, limit: int, offset: int, total_count:int):
        self.request = request
        self.limit = limit
        self.offset = offset
        self.total_count = total_count

    def build_url(self, limit: int, offset: int):
        base = str(self.request.url).split("?")[0]
        params = urlencode({"limit": limit, "offset": offset})
        return f"{base}?{params}"

    def previous(self):
        if self.offset <= 0:
            return None

        prev_offset = max(self.offset - self.limit, 0)
        return self.build_url(self.limit, prev_offset)

    def next(self):
        next_offset = self.offset + self.limit

        if next_offset >= self.total_count:
            return None

        return self.build_url(self.limit, next_offset)
