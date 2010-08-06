declare namespace ub='bill';
for $bill in collection('/db/skyline/bills/')
    let $account := $bill/ub:bill/@account
    let $id:= $bill/ub:bill/@id
    let $recharges := $bill//ub:utilbill[@service="Gas"]/ub:recharges/text()
    let $measuredusage := fn:sum($bill//ub:measuredusage[@service="Gas"]//ub:register[@shadow="true"]/ub:total/text())
where
    xs:decimal(fn:sum($bill//ub:measuredusage[@service="Gas"]//ub:register[@shadow="true"]/ub:total/text())) > 0
    and
    xs:decimal($bill//ub:utilbill[@service="Gas"]/ub:recharges/text()) > 0
return
<thermvalue account="{$account}" id="{$id}">
<charge>{$recharges}</charge>
<therms>{$measuredusage}</therms>
<value>{fn:round((xs:decimal($recharges) div xs:decimal($measuredusage))*100) div 100}</value>
</thermvalue>
