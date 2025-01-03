Evaluation

Text/Textarea
Admin input examples:
operator: 'eq'
value: "some text"

operator: 'contains'  # if you add this operator
value: "partial text"

Number
Admin input examples:
operator: 'gt'
value: "100"

operator: 'lte'
value: "50.5"

Boolean
Admin input examples:
operator: 'eq'
value: "true"  # or "1" or "yes"

operator: 'ne'
value: "false"  # or "0" or "no"

Choice (Single)
Admin input examples:
operator: 'eq'
value: "option1"

operator: 'ne'
value: "option2"

Multiple Choice
Admin input examples:
operator: 'eq'
value: "option1,option2"  # Must match exactly these options

operator: 'gt'
value: "2"  # More than 2 options selected

operator: 'ne'
value: เปิดหน้าบัญชี,ขอเครดิตให้กับบริษัท  # Any selection except exactly these options will evaliuate to True