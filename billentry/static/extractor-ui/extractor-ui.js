tasks=[];

$(document).ready(function() { 
	//Assign id-specific function to each run button
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
		//get appropriate row
		task_table_row = $('#results tr[id='+ elem.task_id +']');

		$.post("/test-status/"+task_id, function(data){
			total_count =  data.total_count;
			all_count =  data.all_count;
			any_count =  data.any_count;
			fields = {}
			Object.keys(data.fields).forEach(function(key, index){
				fields[key]=data.fields[key];
			});

			task_table_row.children("td[header=status]").text(data.state);
			task_table_row.children("td[header=total_count]").text(total_count);
			task_table_row.children("td[header=all_count]").text(all_count);
			task_table_row.children("td[header=any_count]").text(any_count);
			//update field values
			task_table_row.children("td.field").each(function(index, elem){
				$(elem).text(fields[$(elem).attr("header")]);
			});
		});
	});
}

function runExtractor(extractor_id){
	utility_id = $("select[name="+extractor_id+"]").val(); 
	postParameters = {extractor_id:extractor_id, utility_id:(utility_id == "" ? null : utility_id)};
	utiltiy_name = $("option[value="+utility_id+"]:first").text()
	$.post("/run-test", postParameters, function(data, status, request){
		task_id = data.task_id;
		bills_to_run = data.bills_to_run;
		tasks.push({
			extractor_id: extractor_id,
			utility_id: (utility_id=="" ? "None" : utility_id),
			task_id:task_id, 
		});

		// set up table row for this task
		//TODO extractor_id could be ambiguous
		table_row = '<tr id="'+task_id+'">\n' + 
		'<td header="job_id">' + tasks.length + '</td>\n' + 
		'<td header="extractor_id">'+ extractor_id + '</td>\n' + 
		'<td header="utility_name">'+ utiltiy_name+'</td>\n' + 
		'<td header="status"></td>\n' + 
		'<td header="bills_to_run">' + bills_to_run + '</td>\n' + 
		'<td header="total_count"></td>\n' + 
		'<td header="all_count"></td>\n' + 
		'<td header="any_count"></td>\n'; 
		$('#results thead td.field').each(function(index, elem){
			table_row += '<td class="field" header="'+$(elem).attr('id')+'"></td>\n';
		})
		table_row += '</tr>\n'
		$("#results tbody").append(table_row);
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