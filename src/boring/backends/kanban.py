"""Kanban (Outline) backend implementation."""

import re
from typing import Optional, List, Dict, Any

import httpx

from .base import BackendClient, TaskItem, BoardInfo, SectionInfo


def remove_vietnamese_accents(text: str) -> str:
    vietnamese_map = {
        'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
        'ă': 'a', 'ằ': 'a', 'ắ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
        'â': 'a', 'ầ': 'a', 'ấ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
        'đ': 'd',
        'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
        'ê': 'e', 'ề': 'e', 'ế': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
        'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
        'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
        'ô': 'o', 'ồ': 'o', 'ố': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
        'ơ': 'o', 'ờ': 'o', 'ớ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
        'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
        'ư': 'u', 'ừ': 'u', 'ứ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
        'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y',
    }
    
    result = []
    for char in text.lower():
        result.append(vietnamese_map.get(char, char))
    
    return ''.join(result)


def generate_document_url(base_url: str, title: str, doc_id: str, url_id: Optional[str] = None) -> str:
    slug = remove_vietnamese_accents(title)
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    
    if url_id:
        short_id = url_id
    else:
        short_id = doc_id.replace('-', '')[-10:]
    
    return f"{base_url}/doc/{slug}-{short_id}"


class KanbanBackend(BackendClient):

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        board_id: Optional[str] = None,
        list_id: Optional[str] = None,
        done_list_id: Optional[str] = None,
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.board_id = board_id
        self.list_id = list_id
        self.done_list_id = done_list_id

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _post(self, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        if not self.base_url:
            raise Exception("Kanban base URL not configured. Run 'boring setup' first.")
        if not self.api_key:
            raise Exception("Kanban API key not configured. Run 'boring setup' first.")

        with httpx.Client(verify=False) as client:
            response = client.post(
                f"{self.base_url}{endpoint}",
                headers=self._headers(),
                json=data or {},
            )
            response.raise_for_status()
            json_data = response.json()
            if isinstance(json_data, dict) and "data" in json_data:
                return json_data["data"]
            return json_data

    def _map_priority(self, card_detail: Dict[str, Any]) -> Optional[str]:
        priorities = card_detail.get("priorities", [])
        if not priorities:
            p = card_detail.get("priority")
            if p is not None:
                priority_map = {0: "None", 1: "Low", 2: "Medium", 3: "High", 4: "Urgent"}
                return priority_map.get(p, "None")
            return None
        
        return ", ".join([p.get("name", "") for p in priorities if p.get("name")])

    def _fetch_document_info(self, doc_id: str) -> Optional[str]:
        try:
            doc_info = self._post("/api/documents.info", {"id": doc_id})
            return doc_info.get("urlId")
        except Exception:
            return None

    def _fetch_and_process_activities(self, card_id: str) -> tuple[List[Dict[str, Any]], str, List[Dict[str, str]]]:
        try:
            activities = self._post("/api/kanban.cards.activities", {"cardId": card_id})
            if not activities:
                return [], "", []
        except Exception as e:
            return [], "", []

        comments_list = []
        markdown_parts = []
        sorted_activities = sorted(activities, key=lambda x: x.get("createdAt", ""))
        related_docs_dict = {}

        for activity in sorted_activities:
            name = activity.get("name")
            data = activity.get("data", {})
            
            if name == "kanban_cards.comment":
                actor = activity.get("actor", {})
                created_at = activity.get("createdAt", "")
                
                content = data.get("comment", "")
                author = actor.get("name", "Unknown")
                replies = data.get("replies", [])

                comments_list.append({
                    "content": content,
                    "author": author,
                    "created_at": created_at,
                    "replies": replies
                })

                markdown_parts.append(self._format_comment_node(content, author, created_at, replies, level=0))
            
            elif name == "kanban_cards.add_document":
                doc_id = data.get("documentId")
                doc_title = data.get("documentTitle")
                
                if doc_id and doc_title:
                    doc_url_id = self._fetch_document_info(doc_id)
                    related_docs_dict[doc_id] = {
                        "title": doc_title,
                        "urlId": doc_url_id
                    }
                    
            elif name == "kanban_cards.remove_document":
                doc_id = data.get("documentId")
                if doc_id in related_docs_dict:
                    del related_docs_dict[doc_id]

        comments_markdown = ""
        if markdown_parts:
            comments_markdown = "\n\n---\n\n## Comments\n\n" + "\n".join(reversed(markdown_parts))
            
        related_docs = [{"id": k, "title": v["title"], "urlId": v.get("urlId")} for k, v in related_docs_dict.items()]
        return comments_list, comments_markdown, related_docs

    def _format_comment_node(self, content: str, author: str, created_at: str, replies: List[Dict[str, Any]], level: int) -> str:
        indent = "  " * level
        timestamp = created_at.split("T")[0] if "T" in created_at else created_at
        
        markdown = f"{indent}- **{author}** [{timestamp}]: {content}\n"
        
        for reply in replies:
            r_content = reply.get("content", "")
            r_author = reply.get("createdBy", {}).get("name", "Unknown")
            r_created_at = reply.get("createdAt", "")
            r_replies = reply.get("replies", [])
            
            markdown += self._format_comment_node(r_content, r_author, r_created_at, r_replies, level + 1)
            
        return markdown

    def list_boards(self) -> List[BoardInfo]:
        data = self._post("/api/kanban.boards.list")

        boards = []
        for board in data if isinstance(data, list) else []:
            boards.append(BoardInfo(id=board["id"], name=board["name"]))

        return boards

    def get_board_info(self, board_id: str) -> Dict[str, Any]:
        return self._post("/api/kanban.boards.info", {"id": board_id})

    def list_sections(self, board_id: str) -> List[SectionInfo]:
        board_info = self.get_board_info(board_id)

        sections = []
        for col in board_info.get("lists", []):
            sections.append(
                SectionInfo(id=col["id"], name=col["name"], board_id=board_id)
            )

        return sections

    def list_tasks(
        self, section_id: str, labels: Optional[List[str]] = None
    ) -> List[TaskItem]:
        if not self.board_id:
            raise Exception("Kanban board ID not configured. Run 'boring setup' first.")

        board_info = self.get_board_info(self.board_id)

        task_items = []
        label_filter = set(lbl.lower() for lbl in labels) if labels else None

        cards = []
        for lst in board_info.get("lists", []):
            if lst.get("id") == section_id:
                cards = lst.get("cards", [])
                break
        
        if not cards:
            cards = board_info.get("cards", [])

        for card in cards:
            if card.get("listId") and card.get("listId") != section_id:
                continue

            try:
                task_detail = self.get_task_detail(card["id"])
            except Exception:
                continue

            if label_filter and not any(
                lbl.lower() in label_filter for lbl in task_detail.labels
            ):
                continue

            task_items.append(task_detail)

        return task_items

    def get_task_detail(self, task_id: str) -> TaskItem:
        card_detail = self._post("/api/kanban.cards.info", {"id": task_id})
        comments, comments_markdown, related_docs = self._fetch_and_process_activities(task_id)

        title = card_detail.get("title", "")
        description = card_detail.get("description", "")
        priority_str = self._map_priority(card_detail)
        due_date = card_detail.get("dueDate")
        card_labels = card_detail.get("tags", [])

        full_markdown = f"# {title}\n"
        full_markdown += "=" * (len(title) + 2) + "\n\n"

        if priority_str:
            full_markdown += f"**Priority:** {priority_str}\n"

        if due_date:
            full_markdown += f"**Due Date:** {due_date}\n"

        if card_labels:
            full_markdown += f"**Labels:** {', '.join(card_labels)}\n"
        
        full_markdown += "\n"

        if description:
            full_markdown += "## Description\n\n"
            full_markdown += description.strip() + "\n"

        if related_docs:
            full_markdown += "\n---\n\n## Related Documents\n\n"
            for doc in related_docs:
                doc_url = generate_document_url(self.base_url, doc['title'], doc['id'], doc.get('urlId'))
                full_markdown += f"- [{doc['title']}]({doc_url})\n"

        if comments_markdown:
            full_markdown += "\n" + comments_markdown.strip() + "\n"

        return TaskItem(
            id=task_id,
            title=title,
            description=full_markdown,
            priority=priority_str,
            due_date=due_date,
            labels=card_labels,
            comments=comments,
        )

    def move_task(
        self, task_id: str, from_section_id: str, to_section_id: str
    ) -> bool:
        try:
            self._post(
                "/api/kanban.cards.move", {"cardId": task_id, "listId": to_section_id}
            )
            return True
        except Exception:
            return False

    def get_backend_type(self) -> str:
        return "kanban"

    def validate_config(self) -> tuple[bool, Optional[str]]:
        if not self.base_url or not self.api_key:
            return False, "Kanban URL and API key required"

        try:
            self.list_boards()
            return True, None
        except Exception as e:
            return False, str(e)
