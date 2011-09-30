// Given an XML document, extract the begin dates that were automatically set during bill roll
// ToDo: evaluate this function across browsers
function getUBPeriods(bill)
{

    var periods = new Array(); // equivalent to {}.  Arrays should not be used for kv pairs

    evaluateXPath(bill, "/ub:bill/ub:utilbill").forEach(function(value, index, array) {


        //value.getElementsByTagNameNS("bill","billperiodend")[0].childNodes[0].nodeValue;

	var periodBegin;
	var periodEnd;

        var periodBeginElem = value.getElementsByTagNameNS("bill","billperiodbegin")[0];
	// a bill will always have a billperiodbegin value
	// TODO: catch this exception should the billperiodbegin not be present
	var periodBegin = periodBeginElem.childNodes[0].nodeValue;

        var periodEndElem = value.getElementsByTagNameNS("bill","billperiodend")[0];
        // TODO: if there is no periodEnd, guess it vs assign periodBegin
	var periodEnd = periodEndElem.hasChildNodes() ? periodEndElem.childNodes[0].nodeValue : periodBegin;

        periods.push(
            {
                'service': value.attributes['service'].value,
                // TODO: don't refer to index 0 w/o error check. therefore make a cover function in xml-support to do such a check
                'begindate': periodBegin,
                'enddate': periodEnd,
            }
        )
    });

    return periods;
}


var globalServiceType = "Gas";
function getActualCharges(bill)
{
    return getCharges(bill, 'actual', globalServiceType);
}
function getHypotheticalCharges(bill)
{
    return getCharges(bill, 'hypothetical', globalServiceType);
}

// Given a XML document with bill actual charges, flatten them out into a two dimensional array
// ToDo: evaluate this function across browsers
function getCharges(bill, type, service)
{

    // build an array based on the bill xml hypothetical charges
    var hc = new Array();
    // this array will have chargegroup-charge pairs and a number of rows for all charges in a chargegroup
    var chargeIndex = 0 

    var chargegroup = evaluateXPath(bill, 
                "/ub:bill/ub:details[@service=\""+service+"\"]/ub:chargegroup");
    // iterate over nodelist - which can't be iterated like an array can be using forEach, or for in.
    for (var cg = 0; cg < chargegroup.length; cg++)
    {

        // chargegroups contain two sets of charges.  Actual, or hypothetical
        var chargesElems = chargegroup[cg].getElementsByTagName("ub:charges");

        for (var ce = 0; ce < chargesElems.length; ce++) {

            var chargesElem = chargesElems[ce];

            // if an actual set of charges, create an array of the charges
            var chargesType = chargesElem.attributes[0].nodeValue;
            if (chargesType == type)
            {

                var charge = chargesElem.getElementsByTagName("ub:charge");
                for (var c = 0; c < charge.length; c++)
                {

                    hc[chargeIndex] = new Array();

                    hc[chargeIndex][0] = chargegroup[cg].attributes[0].nodeValue;

                    if (charge[c].hasAttribute("rsbinding"))
                        hc[chargeIndex][1] = charge[c].attributes.rsbinding.value;

                    var descriptionElem = (charge[c].getElementsByTagName("ub:description"))[0];
                    // if the data is available, get it, otherwise use a null.  However, ext js grid changes
                    // a null into an empty string if focus passes through the cell that is backed by a null
                    // this results in a dirty store though no data changes were intended.
                    hc[chargeIndex][2] = (descriptionElem && descriptionElem.hasChildNodes()) ? descriptionElem.childNodes[0].nodeValue : null;

                    var quantityElem = (charge[c].getElementsByTagName("ub:quantity"))[0];
                    hc[chargeIndex][3] = (quantityElem && quantityElem.hasChildNodes()) ? quantityElem.childNodes[0].nodeValue : null;
                    hc[chargeIndex][4] = (quantityElem && quantityElem.hasAttributes()) ? quantityElem.attributes[0].nodeValue : null;

                    var rateElem = (charge[c].getElementsByTagName("ub:rate"))[0];
                    hc[chargeIndex][5] = (rateElem && rateElem.hasChildNodes()) ? rateElem.childNodes[0].nodeValue : null;
                    hc[chargeIndex][6] = (rateElem && rateElem.hasAttributes()) ? rateElem.attributes[0].nodeValue : null;

                    var totalElem = (charge[c].getElementsByTagName("ub:total"))[0];
                    hc[chargeIndex][7] = (totalElem && totalElem.hasChildNodes()) ? totalElem.childNodes[0].nodeValue : null;
                    var processingnoteElem = (charge[c].getElementsByTagName("ub:processingnote"))[0];
                    hc[chargeIndex][8] = (processingnoteElem && processingnoteElem.hasChildNodes()) ? processingnoteElem.childNodes[0].nodeValue : null;

                    // increment the array index allowing for the next chargegroup charges to be appended.
                    chargeIndex++;
                }
            }
        }
    }

    return hc;
}


function setActualCharges(bill, records)
{
    return setCharges(bill, records, 'actual', globalServiceType);
}

function setHypotheticalCharges(bill, records)
{
    return setCharges(bill, records, 'hypothetical', globalServiceType);
}

// ToDo: evaluate this function across browsers
// records passed in must be ordered by chargegroup, as they are by the GroupingStore
function setCharges(bill, records, type, service)
{

    // enumerate the records
    // for each chargegroup encountered, find the actual charges in xml
    // delete those actual charges
    // reconstruct the actual charges from the records
    // and insert them into the chargegroup

    // given the array of records from the store backing
    // the grid, convert them to XML
 
    // used to track each new chargegroup found in the groupingstore records
    var cg = null;
    // used to track the XML charges that are deleted then recreated
    var charges = null;
    // used to track charges total. see below where it is added to the charges.
    var chargesSubtotal = 0;
    var chargesTotalElem = null;

    for(var r = 0; r < records.length; r++)
    {
        // pick the current record from the grid grouping store and turn it into XML
        var curRec = records[r];

        // a new chargegroup is seen
        if (cg != curRec.data.chargegroup) 
        {
            cg = curRec.data.chargegroup;

            // reset the total
            chargesSubtotal = 0;

            // ToDo: must support multiple <ub:details service=*/>
            // find the associated actual charges
            var actualChargesNodeList = evaluateXPath(bill, 
                "/ub:bill/ub:details[@service=\""+service+"\"]/ub:chargegroup[@type=\""+cg+"\"]/ub:charges[@type=\""+type+"\"]");

            // ToDo: assert only one set of charges came back
            charges = actualChargesNodeList[0];

            // remove only the charge item children leaving the total child behind
            var deleteChildrenNodeList = evaluateXPath(charges, "ub:charge");
            for (var i = 0; i < deleteChildrenNodeList.length; i++)
            {
                charges.removeChild(deleteChildrenNodeList[i]);
            }

            // Get the total element
            // ToDo: assert only one is returned
            chargesTotalElem = evaluateXPath(charges, "ub:total")[0];
            
        }

        // for the currently obtained charges element, add a new child for every iteration of r
        // when a new chargegroup is encountered, set charges to the new set of charges

        // once removed, recreate each charge
        var charge = bill.createElementNS("bill","ub:charge");

        if (curRec.data.rsbinding && curRec.data.rsbinding.length != 0) {
            var rsbinding = bill.createAttribute("rsbinding");
            charge.setAttributeNode(rsbinding);
            charge.attributes.rsbinding.value = curRec.data.rsbinding;
        }

        // and the children of each charge
        if (curRec.data.description && curRec.data.description.length != 0) {
            var description = bill.createElementNS("bill", "ub:description")
            description.appendChild(bill.createTextNode(curRec.data.description));
            charge.appendChild(description);
        }

        if (curRec.data.quantity && curRec.data.quantity.length != 0) {
            var quantity = bill.createElementNS("bill", "ub:quantity");
            if (curRec.data.quantityunits && curRec.data.quantityunits.length != 0) {
                quantity.setAttribute("units", curRec.data.quantityunits);
            }
            quantity.appendChild(bill.createTextNode(curRec.data.quantity));
            charge.appendChild(quantity);
        }

        if (curRec.data.rate && curRec.data.rate.length != 0) {
            var rate = bill.createElementNS("bill", "ub:rate");
            if (curRec.data.rateunits && curRec.data.rateunits.length != 0) {
                rate.setAttribute("units", curRec.data.rateunits);
            }
            rate.appendChild(bill.createTextNode(curRec.data.rate));
            charge.appendChild(rate);
        }

        // there is always a total
        var total = bill.createElementNS("bill", "ub:total");
        total.appendChild(bill.createTextNode(curRec.data.total));
        charge.appendChild(total);

        if (curRec.data.processingnote && curRec.data.processingnote.length != 0) {
            var processingnote = bill.createElementNS("bill", "ub:processingnote");
            processingnote.appendChild(bill.createTextNode(curRec.data.processingnote));
            charge.appendChild(processingnote);
        }

        // finally, add the charge to the current set of charges
        charges.insertBefore(charge, chargesTotalElem);

        // accumulate the total.  Don't like to do this here...
        // Appears to be no good way to get the grouping store group totals
        // So, we totalize here, or forget it and let a downstream program
        // add the totals to the XML doc.
        // avoid float rounding by going integer math
        chargesSubtotal += parseFloat(curRec.data.total*100);
        chargesTotalElem.removeChild(chargesTotalElem.firstChild);
        // TODO div by zero here.  This needs to be ripped out as described above
        chargesTotalElem.appendChild(bill.createTextNode((chargesSubtotal/100).toString()));
    }
}
