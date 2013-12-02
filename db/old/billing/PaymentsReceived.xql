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
            let $paymentreceived := $doc/ub:bill/ub:rebill/ub:paymentreceived/text()


            order by number($doc/ub:bill/@account), number($doc/ub:bill/@id)
            return
                <bill><account>{$account}</account><billseq>{$id}</billseq><addressee>{$addressee}</addressee><serviceaddress>{$serviceaddress}</serviceaddress><issued>{$issued}</issued><periodbegin>{$billperiodbegin}</periodbegin><periodend>{$billperiodend}</periodend><paymentreceived>{$paymentreceived}</paymentreceived></bill>
};

declare function local:allbills() as xs:decimal
{
    round(sum(/ub:bill/ub:rebill/ub:paymentreceived/text())*100) div 100
};
<bills total="{ local:allbills() }">
	{ local:eachbill() }
</bills>
