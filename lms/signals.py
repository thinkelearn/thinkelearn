from django.db.models.signals import post_save
from django.dispatch import receiver

from .emails import send_course_review_notification
from .models import CourseReview


@receiver(post_save, sender=CourseReview)
def notify_staff_on_course_review_save(
    sender, instance: CourseReview, created: bool, **kwargs
):
    """Send staff notifications when a review is created or updated."""
    send_course_review_notification(instance, created=created)
