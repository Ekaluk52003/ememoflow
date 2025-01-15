from django import template

register = template.Library()

@register.simple_tag
def get_dynamic_field_value(document, field_name):
    return document.get_dynamic_field_value(field_name)

@register.filter
def sum_quantity(product_list):
    return sum(item['quantity'] for item in product_list) if product_list else 0