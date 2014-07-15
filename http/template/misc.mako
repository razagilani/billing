<%def name="messagebox()">
    <div class="messagebox">
        ${caller.body()}
    </div>
</%def>

<%def name="warningbox()">
    <div class="warningbox">
        ${caller.body()}
    </div>
</%def>

<%def name="flash_messages()">
    <%
        messages = get_flashed_messages(with_categories=True)
    %>
    %for message in get_flashed_messages(category_filter=['message']):
        <%self:messagebox>${message}</%self:messagebox>
    %endfor
    %for message in get_flashed_messages(category_filter=['warning']):
        <%self:warningbox>${message}</%self:warningbox>
    %endfor
</%def>
