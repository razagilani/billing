tasks = []
fields = {}

$(document).ready(function() { 
	//Assign id-specific function to each run button
	$(".runbtn").each(function(index, elem){
		elem.onclick = function(){
			runExtractor($(this).attr("name"));
		}
	});
	//Load field names into hash
	$("#results thead .field").each(function(index, elem){
		fields[$(elem).attr("id")] = 0;
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
		task_table_row = $('#results tr[id='+ elem.extractor_id +']');

		total_count = 0;
		all_count = 0;
		any_count = 0;
		Object.keys(fields).forEach(function(key, index){
			fields[key] = 0;
		});

		//For each sub-task...
		elem.task_ids.forEach(function(tid, index){
			$.post("/test-status/"+tid, function(data){
				total_count +=  data.total_count;
				all_count +=  data.all_count;
				any_count +=  data.any_count;
				if(data.fields != null){
					Object.keys(data.fields).forEach(function(key, index){
						if (key in fields) {
							fields[key]+=data.fields[key];
						}
						else {
							fields[key] = 0;
						}
					});
				}

				//TODO state different for each sub-task, find better descriptor
				task_table_row.children("td[header=status]").text(data.state);

				//When last sub-task update request is processed, update the table. 
				if (index == task_ids.length - 1){
					task_table_row.children("td[header=total_count]").text(total_count);
					task_table_row.children("td[header=all_count]").text(all_count);
					task_table_row.children("td[header=any_count]").text(any_count);
					//update field values
					task_table_row.children("td.field").each(function(index, elem){
						$(elem).text(fields[$(elem).attr("header")]);
					});
				}
			});
		});

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