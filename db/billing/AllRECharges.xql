xquery version "1.0";

declare namespace ub='bill';
declare option exist:serialize "method=xhtml media-type=text/html"; 

declare function local:eachbill() as node()*
{
    for $collection in xmldb:get-child-collections('/db/skyline/bills/')
        for $doc in fn:collection(concat('/db/skyline/bills/', $collection)) 
            (: $account is an attribute and returns as an attribute in the returned nodes unless turned into string:)
            let $account:= fn:string($doc/ub:bill/@account)
            let $id := fn:string($doc/ub:bill/@id)
            let $addressee := $doc/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:addressee/text()
            let $serviceaddress := $doc/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:street/text()
            let $issued := $doc/ub:bill/ub:rebill/ub:issued/text()
            let $due := $doc/ub:bill/ub:rebill/ub:duedate/text()
            let $billperiodbegin := $doc/ub:bill/ub:rebill/ub:billperiodbegin/text()
            let $billperiodend := $doc/ub:bill/ub:rebill/ub:billperiodend/text()
            let $recharges := $doc/ub:bill/ub:rebill/ub:recharges/text()
            let $revalue := $doc/ub:bill/ub:rebill/ub:revalue/text()
            let $re_gas := $doc/ub:bill/ub:measuredusage[@service="Gas"]/ub:meter/ub:register[@shadow="true"]/ub:total[last()]/text()
            let $re_elec := $doc/ub:bill/ub:measuredusage[@service="Electric"]/ub:meter/ub:register[@shadow="true"]/ub:total[last()]/text()
            let $re_elec_units := $doc/ub:bill/ub:measuredusage[@service="Electric"]/ub:meter/ub:register[@shadow="true"]/ub:units[last()]/text()
            let $re_gas_units := $doc/ub:bill/ub:measuredusage[@service="Gas"]/ub:meter/ub:register[@shadow="true"]/ub:units[last()]/text()
            let $re_elec_rate_disc := $doc/ub:bill/ub:rebill/ub:recharges/text() div $doc/ub:bill/ub:measuredusage[@service="Electric"]/ub:meter/ub:register[@shadow="true"]/ub:total[last()]/text()
            let $re_gas_rate_disc := $doc/ub:bill/ub:rebill/ub:recharges/text() div $doc/ub:bill/ub:measuredusage[@service="Gas"]/ub:meter/ub:register[@shadow="true"]/ub:total[last()]/text()
            let $re_gas_rate := $doc/ub:bill/ub:rebill/ub:revalue/text() div $doc/ub:bill/ub:measuredusage[@service="Gas"]/ub:meter/ub:register[@shadow="true"]/ub:total[last()]/text()
            let $re_elec_rate := $doc/ub:bill/ub:rebill/ub:revalue/text() div $doc/ub:bill/ub:measuredusage[@service="Electric"]/ub:meter/ub:register[@shadow="true"]/ub:total[last()]/text()


            order by number($doc/ub:bill/@account), number($doc/ub:bill/@id)
            return
                <bill><account>{$account}</account><billseq>{$id}</billseq><addressee>{$addressee}</addressee><serviceaddress>{$serviceaddress}</serviceaddress><issued>{$issued}</issued><periodbegin>{$billperiodbegin}</periodbegin><periodend>{$billperiodend}</periodend><revalue>{$revalue}</revalue><rerate>{$re_gas_rate}{$re_elec_rate}</rerate><recharge>{$recharges}</recharge><re>{$re_gas}{$re_elec}</re><reunits>{$re_gas_units}{$re_elec_units}</reunits><rerate>{$re_gas_rate_disc}{$re_elec_rate_disc}</rerate></bill>
};

declare function local:allbills() as xs:decimal
{
    round(sum(/ub:bill/ub:rebill/ub:recharges/text())*100) div 100
};
<bills total="{ local:allbills() }">
	{ local:eachbill() }
</bills>
