## NinesUI

_better name... eventually_

NinesUI is a framework for building `k9s` inspired TUI applications with
Pydantic classes.  Built on top of Textual.

## Git App Example

[![git app example](https://ninesui.wayl.one/gitnine.gif)](https://ninesui.wayl.one/gitnine.mp4)


## SWAPI App Example

[![swapi app example](https://ninesui.wayl.one/swapi.gif)](https://ninesui.wayl.one/swapi.mp4)

## Sorting

ninesui automatically adds sort keys to your app by sorting by the first
available letter of the data.

[![sorting app example](https://ninesui.wayl.one/sort.gif)](https://ninesui.wayl.one/sort.mp4)

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

[![hovering app example](https://ninesui.wayl.one/hover.gif)](https://ninesui.wayl.one/hover.mp4)
