xquery version "1.0";

declare namespace ub='bill';

declare function local:main()
{
    let $prefix := '/db/skyline/bills'
    for $collection in xmldb:get-child-collections($prefix)
        let $path := fn:string-join(($prefix, $collection), '/')
        let $cresult := xmldb:set-collection-permissions($path, 'prod', 'skyline', util:base-to-integer(0744, 8))
        for $resource in xmldb:get-child-resources($path)
            let $rresult := xmldb:set-resource-permissions($path, $resource, 'prod', 'skyline', util:base-to-integer(0744, 8))
            return
            <processed>{$collection}-{$resource}</processed>

};
local:main()

