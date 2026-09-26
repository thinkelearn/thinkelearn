# Audience-Specific Course Page Plan

Status: Agreed implementation plan
Recorded: September 26, 2026

## Objective

Support adult-oriented and child-friendly presentations of an
`ExtendedCoursePage` without creating separate page models or duplicating course
data and business logic.

The first application is the Mindfulness for Kids course series. The existing
adult presentation must remain the default for all current courses.

## Architecture Decision

Keep one `ExtendedCoursePage` model and add an editor-selectable
`target_audience` field with two choices:

- `adults` — the default, using the current course template.
- `children` — using a new child-friendly course template.

`ExtendedCoursePage.get_template()` will select the template from the stored
audience. Both variants will continue to use the same page URL, content,
lessons, enrollment, payment, visibility, prerequisite, progress, review, and
permission logic.

Separate page models are not part of this plan. They would only be reconsidered
if the audiences later require materially different content fields, lesson
types, publishing workflows, permissions, or business rules.

## Scope

This work covers the `ExtendedCoursePage` course-detail page.

It does not include redesigning:

- Course catalogue cards.
- The learner dashboard.
- H5P or SCORM lesson/player pages.
- The global corporate navigation or footer.

Those items may be considered as a separate follow-up after the children’s
course page has been evaluated in use.

## PR 1: Course Page Template Foundation

Suggested title: `refactor(lms): extract shared course page components`

### Purpose

Prepare the existing course template for multiple presentations while producing
no intentional visual or behavioral change.

### Development Phases

1. Capture desktop and mobile baselines of the current adult course page.
2. Extract behavior-heavy sections that must remain consistent between
   presentations, including:
   - Demo and private-course notices.
   - Authentication, enrollment, and checkout states.
   - Course feedback form behavior and rating script.
   - Shared status and empty states where the same markup is useful.
3. Reassemble the existing adult template from the shared components.
4. Add rendering coverage for anonymous, enrolled, and administrator states.
5. Compare before-and-after screenshots to detect visual regressions.

The templates should not be over-abstracted. Heroes, curriculum presentation,
course details, instructors, reviews, and other intentionally audience-specific
regions may remain separate when sharing them would constrain the children’s
design.

### Acceptance Gate

- No database migration or editor-facing field.
- The adult page remains visually equivalent to the baseline.
- Enrollment, checkout, progress, feedback, reviews, and demo access retain
  their current behavior.
- Relevant LMS tests, linting, and the production Tailwind build pass.
- The PR can be deployed independently without a visible product change.

## PR 2: Audience Selection and Children’s Template

Suggested title: `feat(lms): add children’s course page template`

### Phase 1: Model and Editor Support

- Add an `Audience` choices class to `ExtendedCoursePage`.
- Add `target_audience` with `Adults` and `Children` choices.
- Default the field to `Adults` so existing courses remain unchanged.
- Add the field to the Wagtail Course Metadata panel.
- Add migration `0008`; no data backfill is required beyond the default value.

Adding a public catalogue filter by audience is not part of this PR.

### Phase 2: Template Routing

- Add `ExtendedCoursePage.get_template()`.
- Route adult courses to `lms/extended_course_page.html`.
- Route children’s courses to
  `lms/extended_course_page_children.html`.
- Ensure Wagtail preview follows the selected audience.
- Leave `serve()` access control and `get_context()` business logic unchanged.

### Phase 3: Children’s Course Page Design

Retain the corporate navigation and footer while giving the course area a
warmer, more approachable presentation:

- Use the existing cyan, cream, blue, and orange brand colours more prominently.
- Use the course thumbnail as a strong hero visual when available, with a
  graceful no-thumbnail fallback.
- Use balanced headings, shorter visual groupings, and readable line lengths.
- Present course metadata as friendly chips instead of a dense statistics row.
- Present lessons as an approachable learning path.
- Make the primary Start or Continue action visually dominant.
- Use larger rounded surfaces, gentle layered depth, and clear spacing.
- Keep parent-facing enrollment, payment, privacy, and account language clear
  and trustworthy.
- Preserve CMS-authored course content; change presentation and interface labels,
  not substantive course copy.

The first version will not add a new font, JavaScript framework, animation
dependency, or bespoke illustration requirement.

### Phase 4: Responsive and Accessibility Hardening

- Phone: single-column layout, prominent primary action, and no sticky sidebar.
- Tablet: comfortable card widths and a simplified hero composition.
- Desktop: primary content with a supporting enrollment/details panel.
- Support long course titles and missing optional content.
- Preserve visible keyboard focus and sufficient colour contrast.
- Provide interactive targets of at least 40–44 pixels without overlapping hit
  areas.
- Use subtle, interruptible transitions that name their properties explicitly;
  avoid `transition: all`.
- Respect reduced-motion preferences.
- Use balanced wrapping for short headings and appropriate wrapping for body
  content.
- Use concentric radii for closely nested rounded surfaces and subtle shadows
  where cards require depth.

### Phase 5: Automated Verification

Add coverage for:

- New courses defaulting to the adult audience.
- Adult and children’s courses selecting the correct templates.
- Wagtail preview selecting the correct template.
- Audience switching preserving URLs and course relationships.
- Anonymous, enrolled, and administrator rendering under both templates.
- Enrollment, checkout, progress, feedback, and private-demo behavior.
- Courses with and without thumbnails, lessons, reviews, prerequisites, and
  instructors where practical.

Run the relevant LMS tests, the wider test suite in proportion to the changes,
Ruff checks, template rendering checks, and a production Tailwind build.

### Acceptance Gate

- All existing courses remain on the adult presentation by default.
- Changing only `target_audience` switches the course presentation.
- No course data, URL, relationship, enrollment, or access-control behavior
  changes.
- Both templates work in the important authentication and enrollment states.
- The PR includes desktop and mobile screenshots for review.

## Release Plan

1. Deploy the migration and templates while leaving existing courses set to
   `Adults`.
2. Select one children’s course as the initial rollout candidate.
3. Preview it in Wagtail before publishing.
4. Validate it as an anonymous visitor, enrolled learner, and administrator.
5. Publish the audience change.
6. Monitor feedback before converting additional courses.

Rollback is performed by setting the affected course back to `Adults`; no
content migration is needed.

## Optional Follow-Up PR

Suggested title: `feat(lms): extend children’s theme across learner experience`

This is explicitly deferred until the course-detail page has been evaluated. It
may include:

- Children-aware catalogue cards.
- Learner dashboard presentation.
- H5P and SCORM lesson wrappers.
- Completion and progress celebrations.
- Consistent child-friendly labels throughout the learning journey.
