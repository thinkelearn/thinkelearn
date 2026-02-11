"""Forms for LMS user feedback workflows."""

from django import forms

from .models import CourseReview


class CourseFeedbackForm(forms.ModelForm):
    """Create or update a learner's course feedback."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["review_text"].widget.attrs.update(
            {
                "class": "w-full rounded-md border-neutral-300 text-sm focus:border-cyan-500 focus:ring-cyan-500",
            }
        )

    class Meta:
        model = CourseReview
        fields = ["rating", "review_text"]
        widgets = {
            "rating": forms.HiddenInput(),
            "review_text": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "What worked well, and what could be improved?",
                }
            ),
        }
        labels = {
            "rating": "Course rating",
            "review_text": "Written feedback (optional)",
        }
