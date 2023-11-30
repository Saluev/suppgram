from typing import TypeVar, List, Iterator

from suppgram.errors import DataNotFetched

T = TypeVar("T")


class UnavailableList(List[T]):
    def __len__(self) -> int:
        raise DataNotFetched(
            "data for this list have not been fetched from the database"
        )

    def __iter__(self) -> Iterator[T]:
        raise DataNotFetched(
            "data for this list have not been fetched from the database"
        )

    def __getitem__(self, *args, **kwargs) -> List[T]:
        raise DataNotFetched(
            "data for this list have not been fetched from the database"
        )

    def __setitem__(self, *args, **kwargs) -> None:
        raise DataNotFetched(
            "data for this list have not been fetched from the database"
        )

    def __delitem__(self, *args, **kwargs) -> None:
        raise DataNotFetched(
            "data for this list have not been fetched from the database"
        )
