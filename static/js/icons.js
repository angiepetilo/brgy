// Lucide icons for script-built markup. Mirrors the {% icon %} template tag:
// the SVG is decorative (aria-hidden), so always put a text label next to it.
// The sprite URL comes from <body data-icon-sprite="..."> (hashed by collectstatic).
(function () {
    'use strict';

    function spriteUrl() {
        return (document.body && document.body.dataset.iconSprite) || '/static/vendor/lucide/sprite.svg';
    }

    // Returns an <svg> element.
    function iconElement(name, extraClass) {
        var ns = 'http://www.w3.org/2000/svg';
        var svg = document.createElementNS(ns, 'svg');
        svg.setAttribute('class', 'icon icon-' + name + (extraClass ? ' ' + extraClass : ''));
        svg.setAttribute('aria-hidden', 'true');
        svg.setAttribute('focusable', 'false');
        svg.setAttribute('width', '20');
        svg.setAttribute('height', '20');
        var use = document.createElementNS(ns, 'use');
        use.setAttribute('href', spriteUrl() + '#lucide-' + name);
        svg.appendChild(use);
        return svg;
    }

    // Returns markup for innerHTML. `name` must be a literal icon id.
    function icon(name, extraClass) {
        return iconElement(name, extraClass).outerHTML;
    }

    window.BrgyUI = window.BrgyUI || {};
    window.BrgyUI.icon = icon;
    window.BrgyUI.iconElement = iconElement;
})();
