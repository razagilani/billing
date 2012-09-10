xquery version "1.0";

declare namespace ub='bill';


declare function local:main() as node()*
{
    let $accountid := request:get-parameter('id', '')

    for $child in xmldb:get-child-resources(concat('/db/skyline/bills/',$accountid))
    order by $child
    return
            <bill>{$child}</bill>
};
<bills>
	{ local:main() }
</bills>
