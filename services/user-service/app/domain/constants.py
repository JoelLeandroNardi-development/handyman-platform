from __future__ import annotations

from enum import StrEnum

class TableName(StrEnum):
    USERS = "users"

class UserEventType(StrEnum):
    CREATED = "user.created"
    LOCATION_UPDATED = "user.location_updated"
    UPDATED = "user.updated"
    DELETED = "user.deleted"

class DataKey(StrEnum):
    EMAIL = "email"
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    PHONE = "phone"
    NATIONAL_ID = "national_id"
    ADDRESS_LINE = "address_line"
    POSTAL_CODE = "postal_code"
    CITY = "city"
    COUNTRY = "country"
    LATITUDE = "latitude"
    LONGITUDE = "longitude"

class ErrorMessage(StrEnum):
    USER_ALREADY_EXISTS = "User already exists"
    USER_NOT_FOUND = "User not found"

class ResponseMessage(StrEnum):
    DELETED = "deleted"