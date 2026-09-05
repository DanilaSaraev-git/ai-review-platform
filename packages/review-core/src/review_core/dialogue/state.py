from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class DialogueState:
    id: str
    run_id: str
    finding_id: str
    max_member_turns: int | None
    revision: int = 0
    turn_ids: list[str] = field(default_factory=list)
    active_turn_id: str | None = None
    human_decision_recorded: bool = False
    supported: bool = True

    @classmethod
    def new(
        cls, dialogue_id: str, run_id: str, finding_id: str, *, max_member_turns: int | None
    ) -> DialogueState:
        return cls(dialogue_id, run_id, finding_id, max_member_turns)

    def start_turn(self, turn_id: str) -> None:
        if not self.projection()["can_send_message"]:
            raise ValueError(self.projection()["blocked_reason"])
        self.turn_ids.append(turn_id)
        self.active_turn_id = turn_id
        self.revision += 1

    def finish_turn(self, turn_id: str) -> None:
        if self.active_turn_id != turn_id:
            raise ValueError("turn does not own active dialogue generation")
        self.active_turn_id = None
        self.revision += 1

    def projection(self) -> dict[str, object]:
        if not self.supported:
            reason = "dialogue_not_supported"
        elif self.human_decision_recorded:
            reason = "human_decision_recorded"
        elif self.active_turn_id is not None:
            reason = "generation_in_progress"
        elif self.max_member_turns is not None and len(self.turn_ids) >= self.max_member_turns:
            reason = "turn_limit_reached"
        else:
            reason = None
        return {
            "revision": self.revision,
            "state": "generating"
            if self.active_turn_id
            else (
                "closed"
                if reason in {"human_decision_recorded", "turn_limit_reached", "dialogue_not_supported"}
                else "open"
            ),
            "turn_count": len(self.turn_ids),
            "can_send_message": reason is None,
            "blocked_reason": reason,
        }
