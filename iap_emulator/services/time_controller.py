"""Virtual clock for time manipulation and fast-forwarding.

Responsibilities:
- Maintain virtual current time
- Advance time (days, hours, minutes)
- Trigger time-based events (renewals, expirations)
- Process subscriptions due for renewal/expiration
"""

import time
import threading
from typing import Optional

from iap_emulator.state_logger import get_logger

logger = get_logger(__name__)

class TimeController:
    """Virtual clock for time manipulation and fast-forwarding.

    Provides the ability  to fast-forward and automatically process
    time based events (renewals, expirations).

    Args:
        subscription_engine: optional subscription engine object, if missing,
        global instance is used
    """

    def __init__(self, subscription_engine: Optional['SubscriptionEngine'] = None) -> None:
        from iap_emulator.services.subscription_engine import get_subscription_engine

        # thread safety lock
        self._lock = threading.RLock()
        self._virtual_time_millis = int(time.time() * 1000)
        self._time_offset_millis = 0
        self._subscription_engine = subscription_engine or get_subscription_engine()

        logger.info(
            "time_controller initialized",
            virtual_time_millis=self._virtual_time_millis,
        )

    def get_current_time_millis(self) -> int:
        """Get the current virtual time in milliseconds.

        Returns:
            Current virtual time as Unix timestamp in milliseconds.
        """
        with self._lock:
            return self._virtual_time_millis


    def advance_time(
            self,
            days: int = 0,
            hours: int = 0,
            minutes: int =0,
    ) -> dict:
        """Advance virtual time (days, hours, minutes).

        Processes all subscriptions that become due for renewal
        during the time advancement.

        Args:
            days: number of days to advance
            hours: number of hours to advance
            minutes: number of minutes to advance

        Returns:
            Dictionary with:
                - old_time_millis: time before advancement
                - new_time_millis: time after advancement
                - time_advanced_millis: amount of time advanced
                - renewals_processed: list of renewed subscription tokens
                - grace_period_expired: list of subscriptions moved to hold
        Raises
            ValueError: if time values are negative
        """
        if days < 0  or hours < 0 or minutes < 0:
            raise ValueError("Cannot advance time backwards, use negative values arenot allowed.")

        # 1 day = 24 hours = 1440 minutes = 86,400 seconds = 86,400,000 milliseconds
        milliseconds_to_advance = (
            (days*24*60*60*1000) +
            (hours*60*60*1000) +
            (minutes*60*1000)
        )

        if milliseconds_to_advance  == 0:
            current_time = self.get_current_time_millis()
            return {
                "old_time_millis": current_time,
                "new_time_millis": current_time,
                "time_advanced_millis":0,
                "renewals_processed":[],
                "grace_periods_expired":[]
            }

        # update time
        with self._lock:
            old_time = self._virtual_time_millis

            # jump to the future
            self._virtual_time_millis += milliseconds_to_advance
            self._time_offset_millis += milliseconds_to_advance

            new_time = self._virtual_time_millis

            logger.info(
                "time advanced",
                old_time_millis=old_time,
                new_time_millis=new_time,
                days=days,
                hours=hours,
                minutes=minutes,
            )

        renewed_tokens = self._process_renewals(new_time)
        expired_grace_periods = self._process_grace_period_expirations(new_time)

        return {
            "old_time_millis": old_time,
            "new_time_millis": new_time,
            "time_advanced_millis": milliseconds_to_advance,
            "renewals_processed": renewed_tokens,
            "grace_period_expired": expired_grace_periods,
        }

    def _process_renewals(self, current_time_millis: int) -> list[str]:
        """
        Processes all subscriptions that become due for renewal at that time.
        Args:
            current_time_millis: current time
        Returns:
            List of tokens for subscriptions that were renewed

        """
        from iap_emulator.repositories.subscription_store import get_subscription_store
        store = get_subscription_store()
        renewed_tokens = []

        # find all subs
        subscriptions_due = store.get_renewals_due(current_time_millis)

        logger.info(
            "processing renewals",
            current_time_millis=current_time_millis,
            subscriptions_due=len(subscriptions_due),
        )

        # renew each subscription
        for subscription in subscriptions_due:
            try:
                renewed = self._subscription_engine.renew_subscription(
                    token=subscription.token,
                    renewal_time_millis=subscription.expiry_time_millis,
                )
                renewed_tokens.append(renewed.token)

                logger.debug(
                    "subscription renewed by time controller",
                    token = subscription.token[:20],
                    subscription_id = subscription.subscription_id,
                    new_expiry = renewed.expiry_time_millis,
                )

            except Exception as e:
                logger.error(
                    "subscription renewal failed",
                    token=subscription.token[:20] + "...",
                    subscription_id = subscription.subscription_id,
                    error=str(e)
                )
        if renewed_tokens:
            logger.info(
                "subscription renewal completed",
                count=len(renewed_tokens),
            )
        return renewed_tokens

    def _process_grace_period_expirations(self, current_time_millis: int) -> list[str]:
        """Process grace periods that have expired
        Transitions subscriptions from IN_GRACE_PERIOD to ON_HOLD when their
        grace period expires.
        Args:
            current_time_millis: current virtual time
        Returns:
            List of tokens for subscriptions that moved to ON_HOLD
        """

        transitioned = self._subscription_engine.process_grace_period_expirations(
            current_time_millis=current_time_millis,
        )

        expired_tokens = [sub.token for sub in transitioned]
        if expired_tokens:
            logger.info(
                "subscription grace period expired",
                count=len(expired_tokens), current_time_millis=current_time_millis,
            )

        return expired_tokens

    def set_time(self, timestamp_millis: int) -> dict:
        """Set virtual time to a specific timestamp.

        This is useful for testing specific scenarios without calculating
        time differences.

        Args:
            timestamp_millis: Unix timestamp in milliseconds to set

        Returns:
            Dictionary with old_time_millis and new_time_millis

        Raises:
            ValueError: If timestamp is in the past (before current virtual time)
        """
        with self._lock:
            old_time = self._virtual_time_millis

            # don't allow going backwards in time
            if timestamp_millis < old_time:
                raise ValueError(
                    f'cannot set time backwards, current: {old_time}, requests new: {timestamp_millis}'
                )

            time_jump = timestamp_millis - old_time

            self._virtual_time_millis = timestamp_millis
            self._time_offset_millis += time_jump

            logger.info(
                "time set",
                old_time_millis=old_time,
                time_jump=time_jump,
                new_time_millis=self._time_offset_millis,
            )

        # process renewals
        renewed_tokens = self._process_renewals(timestamp_millis)
        expired_grace_periods = self._process_grace_period_expirations(timestamp_millis)

        return {
            "old_time_millis": old_time,
            "new_time_millis": timestamp_millis,
            "renewal_processed": renewed_tokens,
            "grace_period_expired": expired_grace_periods
        }

    def reset_time(self) -> dict:
        """Reset virtual time back to real current time."""
        with self._lock:
            old_time = self._virtual_time_millis
            real_current_time = int(time.time() * 1000)
            self._virtual_time_millis = real_current_time
            self._time_offset_millis = 0

            logger.info(
                "time_reset",
                old_time_millis=old_time,
                new_time_millis=real_current_time,
            )

            return {
                "old_time_millis": old_time,
                "new_time_millis": real_current_time,
            }

_time_controller_instance: Optional[TimeController] = None
_controller_lock = threading.Lock()

def get_time_controller() -> TimeController:
    global _time_controller_instance
    if _time_controller_instance is None:
        with _controller_lock:
            if _time_controller_instance is None:
                _time_controller_instance = TimeController()
    return _time_controller_instance

def reset_time_controller() -> None:
    global _time_controller_instance
    with _controller_lock:
        _time_controller_instance = TimeController()
