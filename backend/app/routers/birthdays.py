import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user
from ..models import Birthday, User
from ..schemas import BirthdayIn, BirthdayOut
from ..services import recurrence

router = APIRouter(prefix="/birthdays", tags=["birthdays"])


def _out(b: Birthday, user: User) -> BirthdayOut:
    tz = recurrence.to_zone(b.timezone or user.timezone)
    today = dt.datetime.now(tz).date()
    nxt = recurrence.next_birthday(b.date_of_birth, today)
    return BirthdayOut(
        id=b.id, name=b.name, email=b.email, date_of_birth=b.date_of_birth, custom_message=b.custom_message,
        interests=b.interests, timezone=b.timezone, age=nxt.year - b.date_of_birth.year,
        next_birthday=nxt, days_left=(nxt - today).days,
    )


async def _owned(db: AsyncSession, user: User, birthday_id: int) -> Birthday:
    b = await db.get(Birthday, birthday_id)
    if not b or b.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Birthday not found")
    return b


def _apply(b: Birthday, data: BirthdayIn) -> None:
    b.name = data.name.strip()
    b.email = str(data.email).lower() if data.email else None
    b.date_of_birth = data.date_of_birth
    b.custom_message = data.custom_message
    b.interests = data.interests
    b.timezone = data.timezone


@router.post("", response_model=BirthdayOut, status_code=status.HTTP_201_CREATED)
async def create_birthday(data: BirthdayIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    b = Birthday(user_id=user.id)
    _apply(b, data)
    db.add(b)
    await db.commit()
    return _out(b, user)


@router.get("", response_model=list[BirthdayOut])
async def list_birthdays(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(Birthday).where(Birthday.user_id == user.id))).all()
    return sorted((_out(b, user) for b in rows), key=lambda x: x.days_left)


@router.get("/{birthday_id}", response_model=BirthdayOut)
async def get_birthday(birthday_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return _out(await _owned(db, user, birthday_id), user)


@router.put("/{birthday_id}", response_model=BirthdayOut)
async def update_birthday(birthday_id: int, data: BirthdayIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    b = await _owned(db, user, birthday_id)
    _apply(b, data)
    b.last_wished_year = None if b.last_wished_year is None else b.last_wished_year
    await db.commit()
    return _out(b, user)


@router.delete("/{birthday_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_birthday(birthday_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    b = await _owned(db, user, birthday_id)
    await db.delete(b)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
