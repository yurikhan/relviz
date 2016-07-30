$(function () {

$('input[name=_layout]').click(function (event) {
    $('body').removeClass('horizontal vertical').addClass(event.target.value);
    $('textarea').focus();
});
$('input[name=_layout]:checked').click();

$('textarea').focus().keydown(function (event) {
    if (!event.altKey
            && event.ctrlKey
            && !event.shiftKey
            && event.keyCode == 13) {
        $(event.target.form).submit();
        event.preventDefault();
    }
});

$('form').submit(function (event) {
    var form_data = $(event.target).serializeArray();
    var form_dict = {};
    (form_data.filter(function (pair) { return !pair.name.startsWith('_'); })
              .forEach(function (pair) { form_dict[pair.name] = pair.value; }));
    $(event.target).addClass('busy');
    ($.post(event.target.action, form_dict)
      .fail(function (request, textStatus, errorThrown) {
        $(event.target).removeClass('busy');
        var pre = document.createElement('pre');
        $(pre).text(request.status + ' ' + request.statusText + '\n\n'
                    + request.responseText);
        $('#output').empty().append(pre);
      })
      .done(function (data) {
        $(event.target).removeClass('busy');
        $('#output').empty().append(document.adoptNode(data.documentElement));
        $('#output svg').click(function (event) {
            $('body').toggleClass('zoom-out');
        });
      }));
    event.preventDefault();
});

});
