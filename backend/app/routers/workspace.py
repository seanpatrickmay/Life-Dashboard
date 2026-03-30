from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.config import settings
from app.db.models.entities import User
from app.db.models.workspace import WorkspaceAsset
from app.db.session import get_session
from app.schemas.workspace import (
    WorkspaceApplyTemplateRequest,
    WorkspaceAssetCreateRequest,
    WorkspaceAssetUploadResponse,
    WorkspaceBacklinksResponse,
    WorkspaceBootstrapResponse,
    WorkspaceCreateBlockRequest,
    WorkspaceCreatePageRequest,
    WorkspaceCreateRowRequest,
    WorkspaceCreateViewRequest,
    WorkspaceDatabaseRowsResponse,
    WorkspacePageDetailResponse,
    WorkspaceReorderBlocksRequest,
    WorkspaceSearchResponse,
    WorkspaceTemplateResponse,
    WorkspaceUpdateBlockRequest,
    WorkspaceUpdatePageRequest,
    WorkspaceUpdatePropertyValuesRequest,
    WorkspaceUpdateViewRequest,
    WorkspaceViewResponse,
)
from app.routers._shared import run_project_suggestions
from app.services.workspace_service import WorkspaceService


router = APIRouter(prefix="/workspace", tags=["workspace"])
ASSET_STORAGE_ROOT = Path("/tmp/life_dashboard_workspace_assets")
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB


@router.get("/bootstrap", response_model=WorkspaceBootstrapResponse)
async def get_workspace_bootstrap(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WorkspaceBootstrapResponse:
    service = WorkspaceService(session)
    return await service.get_bootstrap(current_user.id)


@router.get("/pages/{page_id}", response_model=WorkspacePageDetailResponse)
async def get_workspace_page(
    page_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WorkspacePageDetailResponse:
    service = WorkspaceService(session)
    return await service.get_page_detail(current_user.id, page_id)


@router.get("/pages/{page_id}/backlinks", response_model=WorkspaceBacklinksResponse)
async def get_workspace_page_backlinks(
    page_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WorkspaceBacklinksResponse:
    service = WorkspaceService(session)
    return await service.get_page_backlinks(current_user.id, page_id)


@router.post("/pages/{page_id}/recent", status_code=204, response_class=Response)
async def mark_workspace_page_recent(
    page_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    service = WorkspaceService(session)
    await service.mark_recent(current_user.id, page_id)
    return Response(status_code=204)


@router.post("/pages", response_model=WorkspacePageDetailResponse)
async def create_workspace_page(
    payload: WorkspaceCreatePageRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WorkspacePageDetailResponse:
    service = WorkspaceService(session)
    page = await service.create_page(
        current_user.id,
        title=payload.title,
        parent_page_id=payload.parent_page_id,
        kind=payload.kind,
        icon=payload.icon,
        cover_url=payload.cover_url,
        description=payload.description,
        show_in_sidebar=payload.show_in_sidebar,
        database_page_id=payload.database_page_id,
        sort_order=payload.sort_order,
        extra_json=payload.extra_json,
        template_id=payload.template_id,
    )
    if page.legacy_todo_id:
        background_tasks.add_task(run_project_suggestions, current_user.id, [page.legacy_todo_id])
    return await service.get_page_detail(current_user.id, page.id)


@router.patch("/pages/{page_id}", response_model=WorkspacePageDetailResponse)
async def update_workspace_page(
    page_id: int,
    payload: WorkspaceUpdatePageRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WorkspacePageDetailResponse:
    service = WorkspaceService(session)
    updates = payload.model_dump(exclude_unset=True)
    page = await service.update_page(
        current_user.id,
        page_id,
        **updates,
    )
    if "title" in updates and page.legacy_todo_id:
        background_tasks.add_task(run_project_suggestions, current_user.id, [page.legacy_todo_id])
    return await service.get_page_detail(current_user.id, page.id)


@router.delete("/pages/{page_id}", status_code=204, response_class=Response)
async def delete_workspace_page(
    page_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    service = WorkspaceService(session)
    await service.delete_page(current_user.id, page_id)
    return Response(status_code=204)


@router.post("/blocks", response_model=WorkspacePageDetailResponse)
async def create_workspace_block(
    payload: WorkspaceCreateBlockRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WorkspacePageDetailResponse:
    service = WorkspaceService(session)
    await service.create_block(
        current_user.id,
        page_id=payload.page_id,
        after_block_id=payload.after_block_id,
        block_type=payload.block_type,
        text_content=payload.text_content,
        checked=payload.checked,
        data_json=payload.data_json,
    )
    return await service.get_page_detail(current_user.id, payload.page_id)


@router.patch("/blocks/{block_id}", response_model=WorkspacePageDetailResponse)
async def update_workspace_block(
    block_id: int,
    payload: WorkspaceUpdateBlockRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WorkspacePageDetailResponse:
    service = WorkspaceService(session)
    updates = payload.model_dump(exclude_unset=True)
    block = await service.update_block(
        current_user.id,
        block_id,
        **updates,
    )
    return await service.get_page_detail(current_user.id, block.page_id)


@router.delete("/blocks/{block_id}", status_code=204, response_class=Response)
async def delete_workspace_block(
    block_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    service = WorkspaceService(session)
    await service.delete_block(current_user.id, block_id)
    return Response(status_code=204)


@router.post("/blocks/reorder", status_code=204, response_class=Response)
async def reorder_workspace_blocks(
    payload: WorkspaceReorderBlocksRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    service = WorkspaceService(session)
    await service.reorder_blocks(current_user.id, payload.page_id, payload.ordered_block_ids)
    return Response(status_code=204)


@router.get("/databases/{database_id}/rows", response_model=WorkspaceDatabaseRowsResponse)
async def get_workspace_database_rows(
    database_id: int,
    view_id: int | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    relation_property_slug: str | None = Query(None),
    relation_page_id: int | None = Query(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WorkspaceDatabaseRowsResponse:
    service = WorkspaceService(session)
    return await service.get_database_rows(
        current_user.id,
        database_id,
        view_id=view_id,
        offset=offset,
        limit=limit,
        relation_property_slug=relation_property_slug,
        relation_page_id=relation_page_id,
    )


@router.post("/databases/{database_id}/rows", response_model=WorkspacePageDetailResponse)
async def create_workspace_database_row(
    database_id: int,
    payload: WorkspaceCreateRowRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WorkspacePageDetailResponse:
    service = WorkspaceService(session)
    page = await service.create_database_row(
        current_user.id,
        database_id,
        title=payload.title,
        properties=payload.properties,
        template_id=payload.template_id,
    )
    if page.legacy_todo_id:
        background_tasks.add_task(run_project_suggestions, current_user.id, [page.legacy_todo_id])
    return await service.get_page_detail(current_user.id, page.id)


@router.patch("/pages/{page_id}/properties", response_model=WorkspacePageDetailResponse)
async def update_workspace_page_properties(
    page_id: int,
    payload: WorkspaceUpdatePropertyValuesRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WorkspacePageDetailResponse:
    service = WorkspaceService(session)
    page = await service.update_property_values(current_user.id, page_id, values=payload.values)
    if page.legacy_todo_id and "title" in payload.values:
        background_tasks.add_task(run_project_suggestions, current_user.id, [page.legacy_todo_id])
    return await service.get_page_detail(current_user.id, page.id)


@router.post("/databases/{database_id}/views", response_model=WorkspaceDatabaseRowsResponse)
async def create_workspace_view(
    database_id: int,
    payload: WorkspaceCreateViewRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WorkspaceDatabaseRowsResponse:
    service = WorkspaceService(session)
    view = await service.create_view(
        current_user.id,
        database_id,
        name=payload.name,
        view_type=payload.view_type,
        is_default=payload.is_default,
        config_json=payload.config_json,
    )
    return await service.get_database_rows(current_user.id, database_id, view_id=view.id)


@router.patch("/views/{view_id}", response_model=WorkspaceViewResponse)
async def update_workspace_view(
    view_id: int,
    payload: WorkspaceUpdateViewRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WorkspaceViewResponse:
    service = WorkspaceService(session)
    updates = payload.model_dump(exclude_unset=True)
    view = await service.update_view(
        current_user.id,
        view_id,
        **updates,
    )
    return WorkspaceViewResponse.model_validate(view)


@router.get("/search", response_model=WorkspaceSearchResponse)
async def search_workspace(
    q: str = Query(""),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WorkspaceSearchResponse:
    service = WorkspaceService(session)
    return await service.search(current_user.id, q)


@router.get("/templates", response_model=list[WorkspaceTemplateResponse])
async def list_workspace_templates(
    database_id: int | None = Query(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[WorkspaceTemplateResponse]:
    service = WorkspaceService(session)
    templates = await service.list_templates(current_user.id, database_id)
    return [WorkspaceTemplateResponse.model_validate(template) for template in templates]


@router.post("/templates/{template_id}/apply", response_model=WorkspacePageDetailResponse)
async def apply_workspace_template(
    template_id: int,
    payload: WorkspaceApplyTemplateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WorkspacePageDetailResponse:
    service = WorkspaceService(session)
    template = await service._require_template(current_user.id, template_id)
    if template.database_id is None:
        raise HTTPException(status_code=400, detail="Template is not attached to a database")
    page = await service.create_database_row(
        current_user.id,
        template.database_id,
        title=payload.title or template.title or template.name,
        properties=payload.properties,
        template_id=template.id,
    )
    return await service.get_page_detail(current_user.id, page.id)


@router.post("/assets/sign", response_model=WorkspaceAssetUploadResponse)
async def create_workspace_asset_upload(
    payload: WorkspaceAssetCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WorkspaceAssetUploadResponse:
    service = WorkspaceService(session)
    asset, upload_url, public_url = await service.create_asset_upload(
        current_user.id,
        page_id=payload.page_id,
        block_id=payload.block_id,
        name=payload.name,
        mime_type=payload.mime_type,
        size_bytes=payload.size_bytes,
        api_prefix=str(request.base_url).rstrip("/") + settings.api_prefix,
    )
    return WorkspaceAssetUploadResponse(
        asset_id=asset.id,
        upload_url=upload_url,
        public_url=public_url,
        headers={},
        status=asset.status,
    )


@router.put("/assets/{asset_id}/content", status_code=204, response_class=Response)
async def upload_workspace_asset_content(
    asset_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    asset = await session.get(WorkspaceAsset, asset_id)
    if asset is None or asset.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Workspace asset not found")
    ASSET_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or asset.name).suffix
    path = ASSET_STORAGE_ROOT / f"{asset.id}{suffix}"
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum upload size is {MAX_UPLOAD_SIZE // (1024 * 1024)} MB.",
        )
    path.write_bytes(content)
    asset.storage_key = str(path)
    asset.public_url = f"{settings.api_prefix}/workspace/assets/{asset.id}/content"
    asset.status = "uploaded"
    await session.commit()
    return Response(status_code=204)


@router.get("/assets/{asset_id}/content")
async def get_workspace_asset_content(
    asset_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    asset = await session.get(WorkspaceAsset, asset_id)
    if asset is None or asset.user_id != current_user.id or not asset.storage_key:
        raise HTTPException(status_code=404, detail="Workspace asset not found")
    path = Path(asset.storage_key)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Workspace asset file missing")
    return FileResponse(path, media_type=asset.mime_type, filename=asset.name)
