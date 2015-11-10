from django import template
import json


def escape_for_json(parser, token):
    nodelist = parser.parse(('endjsonescape',))
    parser.delete_first_token()
    return EscapedNode(nodelist)


class EscapedNode(template.Node):
    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        content = self.nodelist.render(context)
        return json.dumps(content, separators=(',', ':'))


register = template.Library()
register.tag('jsonescape', escape_for_json)