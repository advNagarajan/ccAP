from app.parsers.json_parser import JsonParser
from app.parsers.csv_parser import CsvParser


PARSERS = {
    "JSON": JsonParser(),
    "CSV": CsvParser()
}