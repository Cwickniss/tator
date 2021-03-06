state_properties = {
    'frame': {
        'description': 'Frame number this state applies to.',
        'type': 'integer',
    },
}

version_properties = {
    'version': {
        'description': 'Unique integer identifying the version.',
        'type': 'integer',
    },
}

state_get_properties = {
    'id': {
        'type': 'integer',
        'description': 'Unique integer identifying the state.',
    },
    'meta': {
        'type': 'integer',
        'description': 'Unique integer identifying the entity type.',
    },
    'media': {
        'description': 'List of media IDs that this state applies to.',
        'type': 'array',
        'items': {'type': 'integer'},
    },
    'localizations': {
        'description': 'List of localization IDs that this state applies to.',
        'type': 'array',
        'items': {'type': 'integer'},
    },
    'attributes': {
        'description': 'Object containing attribute values.',
        'type': 'object',
        'additionalProperties': {'$ref': '#/components/schemas/AttributeValue'},
    },
}

state_spec = {
    'type': 'object',
    'required': ['media_ids', 'type'],
    'additionalProperties': {'$ref': '#/components/schemas/AttributeValue'},
    'properties': {
        'type': {
            'description': 'Unique integer identifying a state type.',
            'type': 'integer',
        },
        'media_ids': {
            'description': 'List of media IDs that this state applies to.',
            'type': 'array',
            'items': {'type': 'integer'},
        },
        'localization_ids': {
            'description': 'List of localization IDs that this state applies to.',
            'type': 'array',
            'items': {'type': 'integer'},
        },
        **version_properties,
        **state_properties,
    },
}

state_update = {
    'type': 'object',
    'properties': {
        **state_properties,
        'attributes': {
            'description': 'Object containing attribute values.',
            'type': 'object',
            'additionalProperties': {'$ref': '#/components/schemas/AttributeValue'},
        },        
        'localization_ids_add': {
            'description': 'List of new localization IDs that this state applies to.',
            'type': 'array',
            'items': {'type': 'integer'},
        },
        'localization_ids_remove': {
            'description': 'List of new localization IDs that this state applies to.',
            'type': 'array',
            'items': {'type': 'integer'},
        },
    },
}

state = {
    'type': 'object',
    'properties': {
        **state_get_properties,
        **version_properties,
        **state_properties,
    },
}

state_trim_update = {
    'type': 'object',
    'required': ['frame', 'endpoint'],
    'properties': {
        'frame' : {
            'description': 'Frame number of new end point',
            'type': 'integer',
            'minimum': 0,
        },
        'endpoint' : {
            'description': 'End point to trim to using the provided frame number.',
            'type': 'string',
            'enum': ['start', 'end'],
        }
    }
}

state_merge_update = {
    'type': 'object',
    'required': ['merge_state_id'],
    'properties': {
        'merge_state_id' : {
            'description': "Unique integer identifying the state whose localizations will merge with this state.",
            'type': 'integer',
        },
    }
}