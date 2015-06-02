task_urls = []

$(document).ready(function() { 
	$(".runbtn").each(function(index, elem){
		elem.onclick = function(){
			runExtractor($(this).attr("name"));
		}
	});
});

function selectall(){
	checkboxes = $("input[type=checkbox]");
	allChecked = true;

	//decide whether to 'select all' or 'select none'
	checkboxes.each(function(index, elem){
		allChecked = allChecked && elem.checked;
	});
	//apply to every check box
	checkboxes.each(function(index, elem){
		elem.checked = allChecked ? false : true;
	});
}

function updateStatus(){
	task_urls.forEach(function(elem){
		$.post(elem, function(data){
			console.log(data);
		});
	}) 
}

function runExtractor(extractor_id){
	utility_id = $("select[name="+extractor_id+"]").val();
	postParameters = {extractor_id:extractor_id, utility_id:utility_id};
	$.post("/run-test", postParameters, function(data, status, request){
		task_urls.push(request.getResponseHeader('Location'));
	});
}

function runSelected(){
	checkboxes = $("input[type=checkbox]");
	checkboxes.each(function(index, elem){
		if(elem.checked){
			runExtractor($(elem).val());
		}
	});
}