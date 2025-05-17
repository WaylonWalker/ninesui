## NinesUI

_better name... eventually_

NinesUI is a framework for building `k9s` inspired TUI applications with
Pydantic classes.  Built on top of Textual.

## Git App Example

[![git app example](https://ninesui.waylonwalker.com/gitnine.gif)](https://ninesui.waylonwalker.com/gitnine.mp4)


## SWAPI App Example

[![swapi app example](https://ninesui.waylonwalker.com/swapi.gif)](https://ninesui.waylonwalker.com/swapi.mp4)

## Sorting

ninesui automatically adds sort keys to your app by sorting by the first
available letter of the data.

[![sorting app example](https://ninesui.waylonwalker.com/sort.gif)](https://ninesui.waylonwalker.com/sort.mp4)

## Drill In

Pydantic classes with a `drill_in` method can be drilled into, returning either
strings, models, or lists of models.  Notice in the git example below that when
a file is drilled into it returns the log of that file.

[![drill-in app example](https://ninesui.waylonwalker.com/drill-in.gif)](https://ninesui.waylonwalker.com/drill-in.mp4)

## Global Commands

Commands can be ran with context or as a global command.  Capitalized commands
are ran as a global command, they reset the state of the app and do not pass
context.  Notice in the example how `:films` returns the `films` that include
Beru Whitesun Lars, the breadcumbs are updated to reflect this, but `:Films`
resets the breadcrumbs and returns all films.

[![global-commands app example](https://ninesui.waylonwalker.com/global-commands.gif)](https://ninesui.waylonwalker.com/global-commands.mp4)

## Hover

Adding a `hover` method to a model will make it show a hovered display on
hover.  This can be any rich renderable.

``` python
def hover(self):
    return self
```

### Hover Hotkeys

* `h` - toggle hover
* `a` - toggle wide layout

[![hovering app example](https://ninesui.waylonwalker.com/hover.gif)](https://ninesui.waylonwalker.com/hover.mp4)

## Search

Search is done by typing `/` followed by a search term and Enter.  Currently is
simply searches if the exact text is contained anywhere in the model.

[![searching app example](https://ninesui.waylonwalker.com/searchv2.gif)](https://ninesui.waylonwalker.com/searchv2.mp4)
