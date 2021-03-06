
tasks=[];
selected = null;
show_db_matches = false;

$(document).ready(function() { 
	//Assign id-specific function to each run button
	$(".runbtn").each(function(index, elem){
		elem.onclick = function(){
			runExtractor($(this).attr("name"));
		}
	});

	// Loads currently running tasks from the server
	$.post("/get-running-tests", function(data){
		data.tasks.forEach(function(elem){
			tasks.push(elem);
			var utility_name = $("option[value="+elem.utility_id+"]:first").text();
			newRow(elem.task_id, elem.extractor_id, utility_name, "", elem.bills_to_run);
			updateStatus();
		});
	}).fail(failedRequest("get running tests"));
});

//Selects all checkboxes, unless all are already selected, in which case it unselects all
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

//For all current tasks, get updated progress info from the server, and display it.
function updateStatus(){
	tasks.forEach(function(elem){
		$.post("/test-status/"+elem.task_id, function(data){
			elem.data = data;
			displayData(elem, false);
			if($(selected).attr('id') == elem.task_id){
				displayData(elem, true);
			}
		}).fail(failedRequest("update status"));
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
	if (task_data.total_count == undefined){
		$("#results tr[id="+task.task_id+"] td[header=status]").text(task_data.state);
		$("#results tr[id="+task.task_id+"]").addClass("failed");
		return;
	}
	if(isDetailed){
		//results for a single task, sorted by month
		$("#detailed-results-span").css('display', 'inherit');
		$("#detailed-results tbody").empty();
		Object.keys(task_data.dates).forEach(function(elem){
			var percentString;
			if(task_data.dates[elem].total_count > 0){
				percentString = Math.floor((100.0 * task_data.dates[elem].any_count / task_data.dates[elem].total_count));
			} else {
				percentString = "--";
			}
			isZero = (task_data.dates[elem].any_count == 0) ? "zero" : "";
			var table_row = '<tr class="'+isZero+'" id="'+elem+'">\n' + 
			'<td header="date">'+elem+'</td>\n' + 
			'<td header="total_count">'+task_data.dates[elem].total_count+'</td>\n' + 
			'<td header="all_count">'+task_data.dates[elem].all_count+'</td>\n' + 
			'<td header="any_count">'+task_data.dates[elem].any_count+'</td>\n' + 
			'<td header="percentage">'+percentString+'</td>\n';
			$('#detailed-results thead td.field').each(function(index, field){
				var fieldname = $(field).attr('id');
				table_row += '<td class="field" header="'+fieldname+'">' + task_data.dates[elem].fields[fieldname] + '</td>\n';
			});
			table_row += '</tr>';
			$("#detailed-results tbody").append(table_row);
		});
	} else {
		//task summary for a single task
		var task_table_row = $('#results tr[id='+ task.task_id +']');
		var all_count = task_data.all_count;
		var any_count = task_data.any_count;

		if(show_db_matches){
			var total_count = task_data.verified_count;
		} else {
			var total_count = task_data.total_count;
		}

		task_table_row.children("td[header=status]").text(task_data.state);
		task_table_row.children("td[header=total_count]").text(total_count);
		task_table_row.children("td[header=all_count]").text(all_count);
		task_table_row.children("td[header=any_count]").text(any_count);
		//update field values
		task_table_row.children("td.field").each(function(index, elem){
			var fieldname = $(elem).attr("header");
			if(show_db_matches){
				var frac = task_data.fields_fraction[fieldname];
				var percentString = Math.floor(100.0 * frac);
				var val = percentString + "%"
			} else {
				var val = task_data.fields[fieldname];
			}
			if(val != undefined){
				$(elem).text(val);
			}
		});
	}
}

//Start a new task on the server. 
function runExtractor(extractor_id){
	var utility_id = $("select[name="+extractor_id+"]").val(); 
	var num_bills_str = $("input[name=num_bills]").val();
	var date_filter_type = $("select[name=date_filter_type").val();
	var filter_date = $("input[name=filter_date]").val();
	if(num_bills_str == ""){
		var num_bills = -1;
	} else {
		var num_bills = parseInt(num_bills_str);
	}
	var postParameters = {
		extractor_id: extractor_id,
		utility_id: (utility_id == "" ? null : utility_id),
		num_bills: num_bills,
		date_filter_type: date_filter_type,
		filter_date: filter_date,
	};
	var utility_name = $("option[value="+utility_id+"]:first").text()
	$.post("/run-test", postParameters, function(data, status, request){
		var task_id = data.task_id;
		var bills_to_run = data.bills_to_run;
		if(bills_to_run == 0){
			newRow(null, extractor_id, utility_name, "No bills found.", bills_to_run);
			return;
		}
		tasks.push({
			extractor_id: extractor_id,
			utility_id: (utility_id=="" ? "None" : utility_id),
			task_id:task_id, 
			bills_to_run:bills_to_run,
		});

		// set up table row for this task
		newRow(task_id, extractor_id, utility_name, "", bills_to_run);
	}).fail(failedRequest("run test"));
}

// Set up table row for a new task
// If the task contains no bills (ie task_id is null), then set up a new "failed task" line.
function newRow(task_id, extractor_id, utility_name, status, bills_to_run){
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

//Runs all the selected extractors as new tasks
function runSelected(){
	var checkboxes = $("input[type=checkbox]");
	checkboxes.each(function(index, elem){
		if(elem.checked){
			runExtractor($(elem).val());
		}
	});
}

function clamp(x, min, max){
	return Math.max(Math.min(x, max), min);
}

function stopSelectedTask(){
	if(!selected){
		return;
	}
	else{
		job_id = selected.find("td[header=job_id]").text(); 
		task_id = tasks[job_id - 1].task_id;
		$.post("/stop-task/" + task_id, function(data){
			// once task is stopped, update the page.
			updateStatus();
		}).fail(failedRequest("stop task"));
	}
}

function toggleDBMatches(){
	show_db_matches = !show_db_matches;

	// <td id="total_count">Total so far</td>
	total_header_cell = $("#results #total_count");
	if (show_db_matches) {
		total_header_cell.text("Bills verified");
	} else {
		total_header_cell.text("Total so far");
	}

	tasks.forEach(function(elem){
		displayData(elem, false);
	});
}
function failedRequest(action){
	return function (xhr, textStatus, errorThrown){
		var error_msg;
	   	if (xhr.status == 0) {
	       error_msg = "Could not connect to server.";
	   	} else 
	    if (xhr.status == 404) {
	        error_msg = '404: page not found';
	    } else if (xhr.status == 500) {
	        error_msg = "500: server error";
	    } else if (err == 'parsererror') {
	        error_msg = 'parse error';
	    } else if (err == 'timeout') {
	        error_msg = 'timeout';
	    } else {
	       error_msg = 'unhandled exception: ' + xhr.responseText;
	    }

	    var error_header = "Error: Could not "+action+": ";
	    var error_text = '<span style="color:#FF0000">'+error_header+error_msg+'</span>';
		$("#console").html(error_text + " (click to hide)");
		$("#console").css('display', 'inherit');
	};
}

function hideConsole(){
	$("#console").css('display', 'none');
}