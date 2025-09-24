# utils/menu_util.py
from sqlalchemy.orm import Session
from sqlalchemy import or_, select
from app.modules.auth import models
from typing import List, Dict, Any


def build_menu_tree(db: Session, user_no: int, company_no: int) -> List[Dict[str, Any]]:
    """사용자 권한에 따른 메뉴 트리 구성"""

    # 사용자 메뉴 권한 조회
    menu_no_sel = (
        select(models.ComUserMenu.menu_no)
        .where(
            models.ComUserMenu.user_no == user_no,
            models.ComUserMenu.company_no == company_no
        )
    )

    # 권한 메뉴 + Dashboard 조회
    menu_list = (
        db.query(models.ComMenu)
        .filter(
            or_(
                models.ComMenu.menu_no.in_(menu_no_sel),
                models.ComMenu.menu_name == "Dashboard"
            )
        )
        .order_by(models.ComMenu.order_no)
        .distinct()
        .all()
    )

    return _convert_to_tree_structure(menu_list)


def _convert_to_tree_structure(menu_list) -> List[Dict[str, Any]]:
    """메뉴 리스트를 트리 구조로 변환 (private 함수)"""
    # 딕셔너리 변환
    menu_dicts = [
        {
            "menu_no": menu.menu_no,
            "parent_no": menu.parent_no,
            "menu_name": menu.menu_name,
            "path": menu.path,
            "component": menu.component,
            "icon": menu.icon,
            "order_no": menu.order_no,
            "is_visible": menu.is_visible,
            "children": []
        }
        for menu in menu_list
    ]

    # 빠른 검색을 위한 딕셔너리
    menu_dict = {menu['menu_no']: menu for menu in menu_dicts}
    root_menus = []

    for menu in menu_dicts:
        if menu['parent_no'] == 0:
            root_menus.append(menu)
        else:
            parent = menu_dict.get(menu['parent_no'])
            if parent:
                parent['children'].append(menu)

    return root_menus