"""Timeboxing hooks for Task FSM integration (ADR-012, ADR-014).

Automatically creates calendar events when tasks enter 'doing' state
and manages timebox lifecycle through task transitions.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kira.core.events import Event
    from kira.plugin_sdk.context import PluginContext


class TimeboxingManager:
    """Manages timeboxing for tasks via calendar integration.
    
    Features (ADR-012, ADR-014):
    - Creates calendar blocks when task enters 'doing'
    - Uses time_hint for block duration
    - Updates/closes blocks on state changes
    - Reconciles with actual completion time
    
    Example:
        >>> manager = TimeboxingManager(ctx)
        >>> manager.on_task_enter_doing({
        ...     "task_id": "task-123",
        ...     "time_hint": 60,  # 60 minutes
        ... })
        >>> # Creates 1-hour block in calendar
    """
    
    def __init__(self, ctx: PluginContext) -> None:
        """Initialize timeboxing manager.
        
        Parameters
        ----------
        ctx
            Plugin context
        """
        self.ctx = ctx
    
    def on_task_enter_doing(self, event_data: dict[str, Any]) -> None:
        """Handle task entering 'doing' state - create timebox.
        
        Parameters
        ----------
        event_data
            Event payload from task.enter_doing
        """
        task_id = event_data.get("task_id")
        time_hint = event_data.get("time_hint")  # Duration in minutes
        
        if not task_id:
            self.ctx.logger.warning("No task_id in enter_doing event")
            return
        
        self.ctx.logger.info(
            "Creating timebox for task",
            task_id=task_id,
            time_hint=time_hint,
        )
        
        # Determine duration
        if time_hint and isinstance(time_hint, (int, float)):
            duration_minutes = int(time_hint)
        else:
            # Default: 25 minutes (Pomodoro)
            duration_minutes = 25
            self.ctx.logger.debug(
                f"No time_hint provided, using default {duration_minutes}m",
                task_id=task_id,
            )
        
        # Calculate start and end times
        # Start: now or next available slot
        start_time = datetime.now(timezone.utc)
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        # Emit calendar event creation intent
        self.ctx.events.publish(
            "calendar.create_timebox",
            {
                "task_id": task_id,
                "title": f"🎯 {event_data.get('title', task_id)}",
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "description": f"Timebox for [[{task_id}]]",
                "source": "timebox",
                "tags": ["timebox", "work"],
            },
        )
        
        self.ctx.logger.info(
            "Timebox creation requested",
            task_id=task_id,
            duration_minutes=duration_minutes,
            start=start_time.isoformat(),
            end=end_time.isoformat(),
        )
    
    def on_task_enter_done(self, event_data: dict[str, Any]) -> None:
        """Handle task completion - close timebox.
        
        Parameters
        ----------
        event_data
            Event payload from task.enter_done
        """
        task_id = event_data.get("task_id")
        
        if not task_id:
            return
        
        self.ctx.logger.info("Closing timebox for completed task", task_id=task_id)
        
        # Emit timebox close event
        self.ctx.events.publish(
            "calendar.close_timebox",
            {
                "task_id": task_id,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "update_duration": True,  # Adjust to actual time spent
            },
        )
    
    def on_task_enter_blocked(self, event_data: dict[str, Any]) -> None:
        """Handle task blocked - pause/cancel timebox.
        
        Parameters
        ----------
        event_data
            Event payload from task.enter_blocked
        """
        task_id = event_data.get("task_id")
        blocked_reason = event_data.get("blocked_reason", "Unknown")
        
        if not task_id:
            return
        
        self.ctx.logger.info(
            "Pausing timebox for blocked task",
            task_id=task_id,
            reason=blocked_reason,
        )
        
        # Emit timebox pause event
        self.ctx.events.publish(
            "calendar.pause_timebox",
            {
                "task_id": task_id,
                "blocked_reason": blocked_reason,
                "paused_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    
    def on_task_enter_review(self, event_data: dict[str, Any]) -> None:
        """Handle task entering review - mark timebox for review.
        
        Parameters
        ----------
        event_data
            Event payload from task.enter_review
        """
        task_id = event_data.get("task_id")
        reviewer = event_data.get("reviewer")
        
        if not task_id:
            return
        
        self.ctx.logger.info(
            "Marking timebox for review",
            task_id=task_id,
            reviewer=reviewer,
        )
        
        # Emit review timebox event
        self.ctx.events.publish(
            "calendar.mark_review",
            {
                "task_id": task_id,
                "reviewer": reviewer,
                "review_requested_at": datetime.now(timezone.utc).isoformat(),
            },
        )


def setup_timeboxing_hooks(ctx: PluginContext) -> TimeboxingManager:
    """Setup timeboxing hooks for task FSM.
    
    Parameters
    ----------
    ctx
        Plugin context
    
    Returns
    -------
    TimeboxingManager
        Configured manager with hooks registered
    """
    manager = TimeboxingManager(ctx)
    
    # Register FSM hooks
    # Note: In full implementation, these would be registered with TaskFSM
    # For now, subscribe to events
    
    ctx.events.subscribe("task.enter_doing", lambda e: manager.on_task_enter_doing(e.payload))
    ctx.events.subscribe("task.enter_done", lambda e: manager.on_task_enter_done(e.payload))
    ctx.events.subscribe("task.enter_blocked", lambda e: manager.on_task_enter_blocked(e.payload))
    ctx.events.subscribe("task.enter_review", lambda e: manager.on_task_enter_review(e.payload))
    
    ctx.logger.info("Timeboxing hooks registered")
    
    return manager

