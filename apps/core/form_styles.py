"""
Single source of truth for form widget Tailwind classes.

Forms across the project should call :func:`apply_input_styling` in their
``__init__`` to keep the look-and-feel consistent without duplicating long
Tailwind class strings.
"""
from django import forms

INPUT_CLASSES = (
    "mt-1 block w-full rounded-md border border-slate-300 bg-white "
    "px-3 py-2 shadow-sm placeholder:text-slate-400 "
    "focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 "
    "sm:text-sm"
)
CHECKBOX_CLASSES = (
    "h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
)


def apply_input_styling(form: forms.Form) -> None:
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
            css = CHECKBOX_CLASSES
        else:
            css = INPUT_CLASSES
        existing = widget.attrs.get("class", "")
        widget.attrs["class"] = (existing + " " + css).strip()
