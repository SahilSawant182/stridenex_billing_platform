$(document).on('app_ready', function () {

	if (frappe.session.user === "Guest") return;

	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Billing Notification",
			filters: [],
			fields: [
				"message",
				"priority",
				"user",
				"billing_role",
				"owner",
				"from_date",
				"to_date"
			],
			limit_page_length: 5,
			order_by: "creation desc"
		},

		callback: function (r) {

			if (!r.message) return;

			let filtered = filter_notifications(r.message);

			if (!filtered.length) {
				console.log("All Notifications:", r.message);
				console.log("Filtered:", filtered);
				return;
			}

			let combined_msg = filtered
				.map(n => n.message)
				.join(" &nbsp;&nbsp;&nbsp;&nbsp; | &nbsp;&nbsp;&nbsp;&nbsp; ");

			let highest_priority = get_highest_priority(filtered);

			render_static_bar(combined_msg, highest_priority);
		}
	});


	function filter_notifications(records) {

		let session_user = frappe.session.user;
		let roles = frappe.boot.billing_roles || [];
		let now = frappe.datetime.str_to_obj(
			frappe.datetime.now_datetime()
		);

		return records.filter(n => {

			let from_date = n.from_date
				? frappe.datetime.str_to_obj(n.from_date)
				: null;

			let to_date = n.to_date
				? frappe.datetime.str_to_obj(n.to_date)
				: null;

			if (n.owner === session_user)
				return false;

			if (session_user === "Administrator")
				return false;

			let buffer = 5 * 60 * 1000;

			if (from_date && (from_date.getTime() - buffer) > now.getTime())
				return false;

			if (to_date && to_date < now)
				return false;

			// Global notification
			if (!n.user && !n.billing_role)
				return true;

			if (n.user === session_user)
				return true;

			// Role-based
			if (n.billing_role && roles.includes(n.billing_role))
				return true;

			return false;
		});
	}


	function get_highest_priority(records) {

		if (records.some(r => r.priority === "High")) return "High";
		if (records.some(r => r.priority === "Medium")) return "Medium";

		return "Low";
	}


	function render_static_bar(msg, priority) {

	if ($('#billing-static-bar').length) return;

	let bg = "#f6ffed";
	let text = "#135200";
	let border = "#b7eb8f";

	if (priority === "Medium") {
		bg = "#fffbe6";
		text = "#874d00";
		border = "#ffe58f";
	}

	if (priority === "High") {
		bg = "#fff1f0";
		text = "#a8071a";
		border = "#ffa39e";
	}

	let html = `
	<div id="billing-static-bar"
	style="
		background:${bg};
		color:${text};
		border-bottom:1px solid ${border};
		width:100%;
		display:flex;
		align-items:center;
		position:fixed;
		top:50px;
		left:0;
		z-index:9999;
		height:32px;
		font-size:13px;
		box-shadow:0 1px 4px rgba(0,0,0,0.05);
	">

	<i class="fa fa-bell"
	style="margin-left:10px;margin-right:6px;font-size:12px;"></i>

	<div class="marquee-wrapper"
	style="flex:1;overflow:hidden;white-space:nowrap;">

	<div class="marquee-content"
	style="display:inline-block;padding-left:100%;
	animation:marquee-scroll 25s linear infinite;">

	${msg}

	</div>
	</div>

	<div id="close-billing-bar"
	style="
	cursor:pointer;
	font-size:14px;
	height:100%;
	display:flex;
	align-items:center;
	padding:0 10px;
	border-left:1px solid ${border};
	opacity:0.6;
	">&times;</div>
	</div>
	`;

	// Animation CSS
	if (!$('#marquee-style').length) {

		$("<style id='marquee-style'>")
			.prop("type", "text/css")
			.html(`
				@keyframes marquee-scroll {
					0% { transform: translateX(0); }
					100% { transform: translateX(-100%); }
				}

				.marquee-wrapper:hover .marquee-content {
					animation-play-state: paused;
				}

				#billing-static-bar:hover #close-billing-bar {
					opacity:1;
				}
			`).appendTo("head");
	}

	$('body').prepend(html);

	// Push navbar down smoothly
	$('header .navbar').css({
		"top": "32px",
		"transition": "all 0.2s ease"
	});

	// Close action
	$('#close-billing-bar').on('click', function () {
		$('#billing-static-bar').remove();

		$('header .navbar').css("top", "0px");
	});
}

});