tasks=[];
selected = null;

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
	var checkboxes = $("input[type=checkbox]");
	var allChecked = true;

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
		$.post("/test-status/"+elem.task_id, function(data){
			elem.data = data;
			displayData(elem, false);
			if($(selected).attr('id') == elem.task_id){
				displayData(elem, true);
			}
		});
	});
}

//Displays the currently stored data for a task. This may be stale, one should call updateStatus() for a real-time update.
function displayData(task, isDetailed){
	if(!task || !task.data){
		if(isDetailed){
			$("#detailed-results-span").css('display', 'none');
		}
		return;
	}
	var task_data = task.data;
	if(isDetailed){
		$("#detailed-results-span").css('display', 'inherit');
		$("#detailed-results tbody").empty();
		Object.keys(task_data.dates).forEach(function(elem){
			var table_row = '<tr id="'+elem+'">\n' + 
			'<td header="date">'+elem+'</td>\n' + 
			'<td header="total_count">'+task_data.dates[elem].total_count+'</td>\n' + 
			'<td header="all_count">'+task_data.dates[elem].all_count+'</td>\n' + 
			'<td header="any_count">'+task_data.dates[elem].any_count+'</td>\n';
			$('#detailed-results thead td.field').each(function(index, field){
				var fieldname = $(field).attr('id');
				table_row += '<td class="field" header="'+fieldname+'">' + task_data.dates[elem].fields[fieldname] + '</td>\n';
			});
			table_row += '</tr>';
			$("#detailed-results tbody").append(table_row);
		});
	} else {
		var task_table_row = $('#results tr[id='+ task.task_id +']');
		var total_count = task_data.total_count;
		var all_count = task_data.all_count;
		var any_count = task_data.any_count;

		task_table_row.children("td[header=status]").text(task_data.state);
		task_table_row.children("td[header=total_count]").text(total_count);
		task_table_row.children("td[header=all_count]").text(all_count);
		task_table_row.children("td[header=any_count]").text(any_count);
		//update field values
		task_table_row.children("td.field").each(function(index, elem){
			var val = task_data.fields[$(elem).attr("header")];
			if(val != undefined){
				$(elem).text(val);
			}
		});
	}
}

function runExtractor(extractor_id){
	var utility_id = $("select[name="+extractor_id+"]").val(); 
	var postParameters = {extractor_id:extractor_id, utility_id:(utility_id == "" ? null : utility_id)};
	var utility_name = $("option[value="+utility_id+"]:first").text()
	$.post("/run-test", postParameters, function(data, status, request){
		var bills_to_run = data.bills_to_run;
		if(bills_to_run == 0){
			newRow(null, job_id, extractor_id, utility_name, "No bills found.", bills_to_run);
			return;
		}
		var task_id = data.task_id;
		tasks.push({
			extractor_id: extractor_id,
			utility_id: (utility_id=="" ? "None" : utility_id),
			task_id:task_id, 
		});

		// set up table row for this task
		newRow(task_id, job_id, extractor_id, utility_name, "", bills_to_run);
	});
}

// Set up table row for a new task
// If the task contains no bills (ie task_id is null), then set up a new "failed task" line.
function newRow(task_id, job_id, extractor_id, utility_name, status, bills_to_run){
	var table_row;
	if (task_id) {
		table_row += '<tr id="'+task_id+'">\n' + 
		'<td header="job_id">' + tasks.length + '</td>\n';
	} else {
		table_row += '<tr class="failed">\n' + 
			'<td header="job_id"></td>\n';
	}
	table_row += '<td header="extractor_id">'+ extractor_id + '</td>\n' + 
		'<td header="utility_name">'+ utility_name+'</td>\n' + 
		'<td header="status">' + status + '</td>\n' + 
		'<td header="bills_to_run">' + bills_to_run + '</td>\n' + 
		'<td header="total_count"></td>\n' + 
		'<td header="all_count"></td>\n' + 
		'<td header="any_count"></td>\n'; 
	$('#results thead td.field').each(function(index, elem){
		table_row += '<td class="field" header="'+$(elem).attr('id')+'"></td>\n';
	});
	table_row += '</tr>\n';
	$("#results tbody").append(table_row);
	if(task_id){
		$("#results tbody tr:last").click(function(){
			if(selected) {
				selected.removeClass("selected");
				if(selected.is(this)){
					displayData(null, true);
					selected = null;
					return;
				}
			}
			selected = $(this);
			selected.addClass("selected");
			displayData($.grep(tasks, function(elem, index){return elem.task_id == task_id;})[0], true);
		});
	}
}

function runSelected(){
	var checkboxes = $("input[type=checkbox]");
	checkboxes.each(function(index, elem){
		if(elem.checked){
			runExtractor($(elem).val());
		}
	});
}