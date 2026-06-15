import csv
from io import StringIO

from app.models.domain.dataset import Dataset
from app.models.domain.raw_data import RawData
from app.parsers.base import BaseParser


class CsvParser(BaseParser):

    def parse(self, raw_data: RawData) -> Dataset:

        reader = csv.DictReader(StringIO(raw_data.content))

        records = list(reader)

        return Dataset(
            records=records,
            source_type=raw_data.source_type,
            format_type="CSV"
        )