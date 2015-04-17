<%inherit file="base.mako"/>
<%namespace file="form.mako" import="render_form, render_ext_form"/>
<%def name="sectiontitle()">Edit Customer Interest </%def>








<div style="width:${self.attr.page_width}; font-size:14px; margin-left:auto; margin-right:auto; margin-top:20px; padding-left:${self.attr.page_padding}; padding-right:${self.attr.page_padding};">
    <%
    fields = [form.name, form.rate_class, form.street, form.city, form.state,
              form.postal_code, form.use_periods]
    %>
    <div style="padding-left:40px;" id="content_body">

        %if self.extjs():
            ${render_ext_form(self.sectiontitle, fields)}
        %else:
            ${render_form(fields, form.csrf_token, button="Save")}
        %endif
    </div>

</div>