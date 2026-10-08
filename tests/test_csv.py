import pytest

from app.jobs.csv import read_csv

def test_read_csv() -> None:
    rows = read_csv(
        b"full_name,email\nAarav Sharma,aarav@example.com\n",
        10,
    )

    assert rows[0][0] == 2
    assert rows[0][1].name == "Aarav Sharma"

@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"email\na@example.com\n", "full_name"),
        (b"full_name,email\nAarav,not-an-email\n", "Invalid row"),
        (b"full_name,email\n", "at least one"),
    ],
)
def test_bad_csv(data: bytes, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        read_csv(data, 10)