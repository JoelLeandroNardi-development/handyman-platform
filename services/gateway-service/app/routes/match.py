from fastapi import APIRouter, Depends, Request, Query
from typing import List

from ..schemas import MatchRequest, MatchResult
from ..clients import match_request, list_match_logs, delete_match_log
from ..security import get_current_user
from ..rbac import require_role

router = APIRouter()


@router.post("/match", response_model=List[MatchResult], tags=["Match"])
async def match_endpoint(data: MatchRequest, request: Request, user=Depends(get_current_user)):
    require_role(user, ["user", "admin"])
    return await match_request(data.model_dump(), request_id=request.state.request_id, user_payload=user)


@router.get("/match-logs", tags=["Match"])
async def admin_list_match_logs(
    request: Request,
    user=Depends(get_current_user),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    skill: str | None = Query(default=None),
):
    require_role(user, ["admin"])
    return await list_match_logs(request_id=request.state.request_id, user_payload=user, limit=limit, offset=offset, skill=skill)


@router.delete("/match-logs/{log_id}", tags=["Match"])
async def admin_delete_match_log(
    log_id: int,
    request: Request,
    user=Depends(get_current_user),
):
    require_role(user, ["admin"])
    return await delete_match_log(log_id, request_id=request.state.request_id, user_payload=user)
