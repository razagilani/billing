<%inherit file="base.mako"/>
<%def name="sectiontitle()">Customer Interest</%def>

<div style="width:${self.attr.page_width}; margin-left:auto; margin-right:auto; margin-top:20px; padding-left:${self.attr.page_padding}; padding-right:${self.attr.page_padding};">


    <div style="overflow:auto; margin-bottom:20px;">
        <button type="button" style="float:right;" onclick="location.href='${url_for('interest_new')}'">New Customer Interest</button>

    </div>
    <%
    lis = len(interests)
    %>
    %for idx, interest in enumerate(interests):
        <div onclick="location.href='${url_for('interest_view', interest_id=interest.id)}'" class="offer">
            <div style="font-size:16px;">
                <div style="display:inline-block; vertical-align: top; min-width:200px;">
                    <span style="font-weight:bold;">${interest.customer.name}</span>
                    <br/>
                    <span style="font-size:14px;">Interest ID ${interest.id}</span>
                </div>
                ${interest.rate_class.utility.name} <span style="display:inline-block; min-width:60px;">${interest.rate_class.name}</span>${interest.address.street}, ${interest.address.city}, ${interest.address.state}, ${interest.address.postal_code}
            </div>
            <div style="padding:10px 10px 10px 20px;">
                <div style="min-width:120px; display:inline-block;">Interest ID </div>${interest.id}<br/>
                <div style="min-width:120px; display:inline-block;">Total Offers </div>${interest.offers.count()}<br/>
                <div style="min-width:120px; display:inline-block;">Best Rate </div>${interest.best_rate}<br/>
                <div style="min-width:120px; display:inline-block;">Created By </div>${interest.created_by_user.name}<br/>
                <div style="min-width:120px; display:inline-block;">Use Periods </div>${interest.use_periods.count()}
                <br/>
            </div>
            <a href="${url_for('interest_edit', interest_id=interest.id)}" class="offeredit">edit</a>
        </div>
        %if idx + 1 != lis:
            <hr>
        %endif
    %endfor

</div>