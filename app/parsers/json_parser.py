import json

from app.models.dataset import Dataset
from app.models.raw_data import RawData
from app.parsers.base import BaseParser


class JsonParser(BaseParser):

    def parse(self, raw_data: RawData) -> Dataset:

        records = json.loads(raw_data.content)

        if isinstance(records, dict):
            records = [records]

        return Dataset(
            records=records,
            source_type=raw_data.source_type,
            format_type="JSON"
        )