tasks = []

$(document).ready(function() { 
	$(".runbtn").each(function(index, elem){
		elem.onclick = function(){
			runExtractor($(this).attr("name"));
		}
	});
	//setInterval(updateStatus, 1000);
});

function selectAll(){
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
	tasks.forEach(function(elem){
		task_table_row = $('#results tr[id='+ elem.extractor_id +']');

		total_count = 0;
		all_count = 0;
		any_count = 0;

		$.post("/test-status/"+elem.task_ids[0], function(data){
			console.log(data);
			total_count +=  data.total_count;
			all_count +=  data.all_count;
			any_count +=  data.any_count;

			//TODO state different for each sub-task
			task_table_row.children("td[header=status]").text(data.state);
		});

		task_table_row.children("td[header=total_count]").text(total_count);
		task_table_row.children("td[header=all_count]").text(all_count);
		task_table_row.children("td[header=any_count]").text(any_count);
	});
}


function runExtractor(extractor_id){
	utility_id = $("select[name="+extractor_id+"]").val(); 
	postParameters = {extractor_id:extractor_id, utility_id:utility_id};
	utiltiy_name = (utility_id=="" ? "None" : utility_id);
	$.post("/run-test", postParameters, function(data, status, request){
		task_ids = data.task_ids;
		tasks.push({
			extractor_id: extractor_id,
			utility_id: (utility_id=="" ? "None" : utility_id),
			task_ids:task_ids, 
		});

		// set up table row for this task
		//TODO extractor_id could be ambiguous
		table_row = '<tr id="'+extractor_id+'">\n' + 
		'<td header="job_id">' + tasks.length + '</td>\n' + 
		'<td header="extractor_id">'+ extractor_id + '</td>\n' + 
		'<td header="utility_name">'+ utiltiy_name+'</td>\n' + 
		'<td header="status"></td>\n' + 
		'<td header="total_count"></td>\n' + 
		'<td header="all_count"></td>\n' + 
		'<td header="any_count"></td>\n' + 
		'</tr>'
		$("#results tr:last").after(table_row);
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