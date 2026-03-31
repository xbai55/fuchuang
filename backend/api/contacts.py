from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db, User, Contact
from schemas import ContactCreate, ContactUpdate, ContactResponse
from auth import get_current_active_user
from schemas.response import success_response, error_response, ResponseCode

router = APIRouter()


@router.post("/")
async def create_contact(
    contact_data: ContactCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """创建联系人"""
    # 如果设置为监护人，先取消其他联系人
    if contact_data.is_guardian:
        db.query(Contact).filter(
            Contact.user_id == current_user.id,
            Contact.is_guardian == True
        ).update({"is_guardian": False})

    new_contact = Contact(
        user_id=current_user.id,
        name=contact_data.name,
        phone=contact_data.phone,
        relationship=contact_data.relationship,
        is_guardian=contact_data.is_guardian
    )

    db.add(new_contact)
    db.commit()
    db.refresh(new_contact)

    return success_response(
        data=ContactResponse(
            id=new_contact.id,
            name=new_contact.name,
            phone=new_contact.phone,
            relationship=new_contact.relationship,
            is_guardian=new_contact.is_guardian,
            created_at=new_contact.created_at
        ),
        message="创建成功"
    )


@router.get("/")
async def get_contacts(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取联系人列表"""
    contacts = db.query(Contact).filter(Contact.user_id == current_user.id).all()

    items = [
        ContactResponse(
            id=c.id,
            name=c.name,
            phone=c.phone,
            relationship=c.relationship,
            is_guardian=c.is_guardian,
            created_at=c.created_at
        )
        for c in contacts
    ]

    return success_response(data=items)


@router.get("/{contact_id}")
async def get_contact(
    contact_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取单个联系人"""
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.user_id == current_user.id
    ).first()

    if not contact:
        return error_response(ResponseCode.NOT_FOUND, "联系人不存在")

    return success_response(
        data=ContactResponse(
            id=contact.id,
            name=contact.name,
            phone=contact.phone,
            relationship=contact.relationship,
            is_guardian=contact.is_guardian,
            created_at=contact.created_at
        )
    )


@router.put("/{contact_id}")
async def update_contact(
    contact_id: int,
    contact_update: ContactUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """更新联系人"""
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.user_id == current_user.id
    ).first()

    if not contact:
        return error_response(ResponseCode.NOT_FOUND, "联系人不存在")

    # 如果设置为监护人，先取消其他联系人
    if contact_update.is_guardian == True:
        db.query(Contact).filter(
            Contact.user_id == current_user.id,
            Contact.is_guardian == True,
            Contact.id != contact_id
        ).update({"is_guardian": False})

    # 更新字段
    update_data = contact_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(contact, field, value)

    db.commit()
    db.refresh(contact)

    return success_response(
        data=ContactResponse(
            id=contact.id,
            name=contact.name,
            phone=contact.phone,
            relationship=contact.relationship,
            is_guardian=contact.is_guardian,
            created_at=contact.created_at
        ),
        message="更新成功"
    )


@router.delete("/{contact_id}")
async def delete_contact(
    contact_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """删除联系人"""
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.user_id == current_user.id
    ).first()

    if not contact:
        return error_response(ResponseCode.NOT_FOUND, "联系人不存在")

    db.delete(contact)
    db.commit()

    return success_response(message="联系人已删除")
