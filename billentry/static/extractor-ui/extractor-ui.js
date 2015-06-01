function selectall(){
	checkboxes = $("input[type=checkbox]");
	allChecked = true;

	//decide whether to 'select all' or 'select none'
	checkboxes.each(function(index, elem){
		allChecked = allChecked && elem.checked
	});
	//apply to every check box
	checkboxes.each(function(index, elem){
		elem.checked = allChecked ? false : true
	});
}