from __future__ import annotations
from enum import StrEnum

class TableName(StrEnum):
    HANDYMEN = "handymen"
    HANDYMAN_REVIEWS = "handyman_reviews"
    SKILLS_CATEGORIES = "skills_categories"
    SKILLS_CATALOG_ITEMS = "skills_catalog_items"

class HandymanEventType(StrEnum):
    CREATED = "handyman.created"
    LOCATION_UPDATED = "handyman.location_updated"
    UPDATED = "handyman.updated"
    DELETED = "handyman.deleted"

class DataKey(StrEnum):
    EMAIL = "email"
    LATITUDE = "latitude"
    LONGITUDE = "longitude"

class ErrorMessage(StrEnum):
    INVALID_HANDYMAN_SKILLS = "Invalid handyman skills"
    HANDYMAN_ALREADY_EXISTS = "Handyman already exists"
    HANDYMAN_NOT_FOUND = "Handyman not found"
    REVIEW_ALREADY_EXISTS = "Review already exists for this booking"

class ResponseMessage(StrEnum):
    DELETED = "deleted"

class SeedReason(StrEnum):
    ALREADY_PRESENT = "already_present"
    BOOTSTRAPPED = "bootstrapped"

PROFILE_COMPLETENESS_TOTAL_CHECKS = 8