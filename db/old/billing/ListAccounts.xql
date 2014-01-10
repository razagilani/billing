xquery version "1.0";

declare namespace ub='bill';

declare function local:main() as node()*
{
    for $child in xmldb:get-child-collections('/db/skyline/bills/')
    return
            <account>{$child}</account>
};
<accounts>
	{ local:main() }
</accounts>
