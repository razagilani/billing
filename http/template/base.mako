<!DOCTYPE html>
<%
    company_name = 'Nextility'
%>

<html lang="en">
    <head>
        <title>${' - '.join([self.sectiontitle(), company_name])}</title>
    </head>
    <body>
        ${next.body()}
    </body>
</html>