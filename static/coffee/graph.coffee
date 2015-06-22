$ () ->
  edge_line_color = '#F2B1BA'

  drawn_from = undefined

  connections = $.Deferred()
  connections_get = $.get '/connections.json',
    ((data) ->
      console.log 'data', data
      ret ={
        nodes: ({data: {id: name}} for name in data.nodes),
        edges: ({data: {label: edge.label, source: edge.source, target: edge.target}} for edge in data.edges)
      }
      console.log ret
      connections.resolve(ret)
    ), 'json'

  cy = cytoscape {
    container: $('#cy')[0],
    style: cytoscape.stylesheet().selector('node').css({
      'background-color': '#B3767E',
      content: 'data(id)'
    }).selector('edge').css({
      'line-color': edge_line_color,
      'target-arrow-color': '#000',
      'target-arrow-shape': 'triangle',
      width: 2,
      opacity: 0.8,
      #content: 'data(label)'
    }),
    ready: () -> console.log('ready'),
    #layout: {name: 'breadthfirst', fit: true},
    #layout: {name: 'concentric', levelWidth: ((node) -> 1)},
    #layout: {name: 'cose', animate: false, idealEdgeLength: 50},
    layout: {name: 'spread', maxExpandIterations: 10},
    elements: connections.promise()
  }
  cy.edgehandles()

  cy.on 'select', (ev) ->
    cy.$().css({'line-color': edge_line_color})

    iid = ev.cyTarget.id()

    cy.$("edge[source=\"#{ iid }\"]").css({'line-color': '#000'})

    cy.$("edge[target=\"#{ iid }\"]").css({'line-color': '#00F'})

  cy.on 'tap', (ev) ->
    el = ev.cyTarget

    return if el.length

    cy.add {
      group: 'nodes',
      data: {id: 'x'},
      position: ev.cyPosition
    }
