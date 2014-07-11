<%
from billing.data.model import UsePeriod

%>

<%inherit file="base.mako"/>
<%def name="sectiontitle()">Customer Interest ID ${interest.id} - ${interest.customer.name}</%def>

<div style="width:${self.attr.page_width}; margin-left:auto; margin-right:auto; margin-top:20px; padding-left:${self.attr.page_padding}; padding-right:${self.attr.page_padding};">

    <div style="float:right;">
         <a href="${url_for('interest_edit', interest_id=interest.id)}">edit customer interest</a>
         <%doc><button type="button" style="float:right;" onclick="location.href='${url_for('')}'">Update Offers</button></%doc>
    </div>

     <div style="overflow:auto;">
        <div style="font-size:16px;">
            <div style="display:inline-block; vertical-align: top; min-width:200px;">
                <span style="font-weight:bold;">${interest.customer.name}</span>
                <br/><br/>
                <span style="font-size:14px;">Interest ID ${interest.id}</span>
            </div>
            ${interest.rate_class.utility.name} <span style="display:inline-block; min-width:60px;">${interest.rate_class.name}</span>${interest.address.street}, ${interest.address.city}, ${interest.address.state}, ${interest.address.postal_code}
        </div>
        <div style="padding:10px 10px 10px 20px; float:left;">
            <div style="min-width:120px; display:inline-block;">Interest ID </div>${interest.id}<br/>
            <div style="min-width:120px; display:inline-block;">Total Offers </div>${interest.offers.count()}<br/>
            <div style="min-width:120px; display:inline-block;">Best Rate </div>${interest.best_rate}<br/>
            <div style="min-width:120px; display:inline-block;">Created By </div>${interest.created_by_user.name}<br/>
            <div style="min-width:120px; display:inline-block;">Use Periods </div>${interest.use_periods.count()}
        </div>

     </div>

    <div style="margin-top:15px;">Use Periods</div>
    <div style="margin-top:10px; display:table; font-size:12px;">
            <div style="display:table-cell; padding:3px;">Time Start</div>
            <div style="display:table-cell; padding:3px;">Time End</div>
            <div style="display:table-cell; padding:3px;">Quantity</div>
    %for u in interest.use_periods.order_by(UsePeriod.time_start):
        <div style="display:table-row;">
            <div style="display:table-cell; padding:3px;">${u.time_start}</div>
            <div style="display:table-cell; padding:3px;">${u.time_end}</div>
            <div style="display:table-cell; padding:3px;">${u.quantity}</div>
        </div>
    %endfor


    </div>


</div>