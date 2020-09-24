function isOverlapping(events, eventToCheck) {
    /*
    Checks if `eventToCheck` overlaps with any events in `events`.
    Modified from: https://github.com/fullcalendar/fullcalendar/issues/4849#issuecomment-452583317
    */

    const startMoment = moment(eventToCheck.start);
    const endMoment = moment(eventToCheck.end);

    try {

        for (let i = 0; i < events.length; i++) {

            const eventA = events[i];
            const eventAStart = moment(eventA.start);
            const eventAEnd = moment(eventA.end);

            // Start-time in between any of the events
            if (moment(startMoment).isAfter(eventAStart) && moment(startMoment).isBefore(eventAEnd)) {
                return true;
            }

            // End-time in between any of the events
            if (moment(endMoment).isAfter(eventAStart) && moment(endMoment).isBefore(eventAEnd)) {
                return true;
            }

            // Any of the events in between/on the start-time and end-time
            if (moment(startMoment).isSameOrBefore(eventAStart) && moment(endMoment).isSameOrAfter(eventAEnd)) {
                return true;
            }

        }

        return false;

    } catch (error) {
        console.error(error);
        throw error;
    }
}


const options = {
    schedulerLicenseKey: '0320620453-fcs-1597083069',
    aspectRatio: 1.7,
    editable: true,
    selectable: true,
    nowIndicator: true,
    themeSystem: 'bootstrap',
    timeZone: 'local',
    headerToolbar: {
        left: 'today prev,next',
        center: 'title',
        right: 'resourceTimelineDay,resourceTimelineWeek'
    },
    views: { 
        day: { // customize day view to show weekday
            titleFormat: { weekday: 'short', month: 'short', day: 'numeric' }
        },
        week: { // customize week view to exclude year
            titleFormat: { month: 'short', day: 'numeric' }
        }
    },
    initialView: 'resourceTimelineDay',
    resourceAreaHeaderContent: 'Room',
    resourceGroupField: 'room',
    resourceAreaWidth: '25%',
    resourceOrder: 'PK',  // Sorting by this, which is the same for all resources, will ensure fullcalendar does not mess up the correct order from url feed
    resources: {
        url: 'resource_data',
        method: 'POST'
    },
    events: {
        url: 'event_data',
        failure: function() {
            alert('Unexpected error while fetching events.');
        },
    },
    eventOverlap: false,
    firstDay: 1, // start week on Sunday
}

document.addEventListener('DOMContentLoaded', function() {

    var calendarEl = document.getElementById('calendar');
    var calendar = new FullCalendar.Calendar(calendarEl, options);

    /*
    Callback that is triggered when a date/time selection is made.
    */
    calendar.on('select', function(info) {
        if (isOverlapping(info.resource.getEvents(), info)) {
            alert('Your booking overlaps with another booking or a reserved time.');
        } else {

            const startTime = new Date(info.startStr).toLocaleString()
            const endTime = new Date(info.endStr).toLocaleString()

            var confirmation_message = 'Create a reservation in ' + info.resource.extendedProps.room + ' ' 
                                        + info.resource.title + ' from ' + startTime + ' to ' + endTime + '?';

            if (confirm(confirmation_message)) {
                
                $.ajax({
                    type: 'POST',
                    url: ('event_create'),
                    contentType: 'application/json;charset=UTF-8',
                    data: JSON.stringify({
                        start: info.startStr,
                        end: info.endStr,
                        resourceId: info.resource.id,
                        resourceName: info.resource.extendedProps.room + ' - ' + info.resource.title,
                        viewStart: info.view.currentStart,
                        viewEnd: info.view.currentEnd,
                    }),

                    success: function (data) {
                        // Refresh calendar on success
                        // Can also reload page with location.reload(); if the reservation history needs to be refreshed
                        calendar.refetchEvents();
                    },

                    error: function (xhr, status, error) {
                        calendar.refetchEvents();
                        alert(xhr.responseText);
                    },

                });

            } else {
                calendar.refetchEvents();
            }
        }
    });
    
    /*
    Callback that is triggered when resizing stops and the event has changed in duration.
    */
    calendar.on('eventResize', function(info) {

        const startTime = new Date(info.event.startStr).toLocaleString()
        const endTime = new Date(info.event.endStr).toLocaleString()

        var confirmation_message = 'Modify reservation to the same locaiton but from ' + startTime 
                                    + ' to ' + endTime + '?';
        
        var payload = {
            PK: info.event.extendedProps.PK,
            SK: info.event.extendedProps.SK,
            uni: info.event.extendedProps.uni,
            start: info.event.startStr,
            end: info.event.endStr,
        }

        if (confirm(confirmation_message)) {

            $.ajax({
                type: 'POST',
                url: ('event_modify'),
                contentType: 'application/json;charset=UTF-8',
                data: JSON.stringify(payload),
                success: function (data) {
                    calendar.refetchEvents();
                },
                error: function (xhr, status, error) {
                    calendar.refetchEvents();
                    alert(xhr.responseText);
                },
            });

        } else {
            info.revert();
            calendar.refetchEvents();
        }
    })

    /*
    Callback that is triggered when dragging stops and the event has moved to a different day/time.
    */
    calendar.on('eventDrop', function(info) {

        const startTime = new Date(info.event.startStr).toLocaleString()
        const endTime = new Date(info.event.endStr).toLocaleString()

        if (info.oldResource) {
            var confirmation_message = 'Modify reservation to ' + info.newResource.extendedProps.room + ' ' 
                                        + info.newResource.title + ' from ' + startTime + ' to ' + endTime + '?';

            var payload = {
                PK: info.event.extendedProps.PK,
                SK: info.event.extendedProps.SK,
                uni: info.event.extendedProps.uni,
                start: info.event.startStr,
                end: info.event.endStr,
                newResourceId: info.newResource.id,
                newResourceName: info.newResource.extendedProps.room + ' - ' + info.newResource.title
            }
        } else {
            var confirmation_message = 'Modify reservation to the same locaiton but from ' + startTime 
            + ' to ' + endTime + '?';
            
            var payload = {
                PK: info.event.extendedProps.PK,
                SK: info.event.extendedProps.SK,
                uni: info.event.extendedProps.uni,
                start: info.event.startStr,
                end: info.event.endStr,
            }
        }

        if (confirm(confirmation_message)) {

            $.ajax({
                type: 'POST',
                url: ('event_modify'),
                contentType: 'application/json;charset=UTF-8',
                data: JSON.stringify(payload),
                success: function (data) {
                    calendar.refetchEvents();
                },
                error: function (xhr, status, error) {
                    calendar.refetchEvents();
                    alert(xhr.responseText);
                },
            });

        } else {
            info.revert();
            calendar.refetchEvents();
        }
    })

    calendar.render();

    /*
    Refetch events after returning from a given amount (milliseconds) of inactivity; Using https://github.com/shawnmclean/Idle.js
    */
    const AWAY_TIMEOUT = 60000;
    var awayBackCallback = function() {
        calendar.refetchEvents();
    };
    var idle = new Idle({
        onAwayBack: awayBackCallback,
        awayTimeout: AWAY_TIMEOUT
    }).start();

});
