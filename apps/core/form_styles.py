"""
Single source of truth for form widget Tailwind classes.

Forms across the project should call :func:`apply_input_styling` in their
``__init__`` to keep the look-and-feel consistent without duplicating long
Tailwind class strings.
"""
from django import forms

INPUT_CLASSES = (
    "mt-1 block w-full rounded-lg border border-slate-300 bg-white "
    "px-3.5 py-2.5 text-sm shadow-sm placeholder:text-slate-400 "
    "transition-colors duration-200 "
    "focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30 "
    "disabled:bg-slate-50 disabled:text-slate-500"
)
CHECKBOX_CLASSES = (
    "h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-2 focus:ring-brand-500/30 transition-colors"
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
