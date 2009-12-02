<?xml version="1.0" encoding="UTF-8"?>
<structure version="9" htmlmode="strict" relativeto="*SPS" encodinghtml="UTF-8" encodingrtf="ISO-8859-1" encodingpdf="UTF-8" useimportschema="1" embed-images="1">
	<parameters/>
	<schemasources>
		<namespaces/>
		<schemasources>
			<xsdschemasource name="XML" main="1" schemafile="UtilityBill.xsd" workingxmlfile="sample\Pepco-3091-4490-03-20080908.xml">
				<xmltablesupport/>
				<textstateicons/>
			</xsdschemasource>
		</schemasources>
	</schemasources>
	<modules/>
	<flags>
		<scripts/>
		<globalparts/>
		<designfragments/>
		<pagelayouts/>
	</flags>
	<scripts>
		<script language="javascript"/>
	</scripts>
	<importedxslt/>
	<globalstyles/>
	<mainparts>
		<children>
			<globaltemplate subtype="main" match="/">
				<children>
					<documentsection>
						<properties columncount="1" columngap="0.50in" headerfooterheight="fixed" pagemultiplepages="0" pagenumberingformat="1" pagenumberingstartat="auto" pagestart="next" paperheight="11in" papermarginbottom="0.79in" papermarginfooter="0.30in" papermarginheader="0.30in" papermarginleft="0.60in" papermarginright="0.60in" papermargintop="0.79in" paperwidth="8.50in"/>
					</documentsection>
					<template subtype="source" match="XML">
						<children>
							<newline/>
							<paragraph paragraphtag="h1">
								<children>
									<text fixtext="Skyline Normalized Utility Bill (SNUB)"/>
								</children>
							</paragraph>
							<text fixtext="Skyline Utility Bill Reference: "/>
							<template subtype="element" match="utilitybill">
								<children>
									<template subtype="attribute" match="id">
										<children>
											<content/>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<newline/>
							<newline/>
							<paragraph paragraphtag="h2">
								<children>
									<text fixtext="Customer Records"/>
								</children>
							</paragraph>
							<text fixtext="Utility Account Number: "/>
							<template subtype="element" match="utilitybill">
								<children>
									<template subtype="element" match="car">
										<children>
											<template subtype="element" match="accountnumber">
												<children>
													<content/>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<newline/>
							<newline/>
							<text fixtext="Billing Address: "/>
							<template subtype="element" match="utilitybill">
								<children>
									<template subtype="element" match="car">
										<children>
											<template subtype="element" match="billingaddress">
												<children>
													<content/>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<newline/>
							<text fixtext="Service Address: "/>
							<template subtype="element" match="utilitybill">
								<children>
									<template subtype="element" match="car">
										<children>
											<template subtype="element" match="serviceaddress">
												<children>
													<content/>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<newline/>
							<newline/>
							<paragraph paragraphtag="h2">
								<children>
									<text fixtext="Utility Records"/>
								</children>
							</paragraph>
							<text fixtext="Customer Service: "/>
							<template subtype="element" match="utilitybill">
								<children>
									<template subtype="element" match="uar">
										<children>
											<template subtype="element" match="customerservice">
												<children>
													<content/>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<newline/>
							<text fixtext="Utility Payment Location: "/>
							<template subtype="element" match="utilitybill">
								<children>
									<template subtype="element" match="uar">
										<children>
											<template subtype="element" match="paymentlocation">
												<children>
													<content/>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<newline/>
							<text fixtext="Utility Emergency Contact: "/>
							<template subtype="element" match="utilitybill">
								<children>
									<template subtype="element" match="uar">
										<children>
											<template subtype="element" match="emergencycontact">
												<children>
													<content/>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<newline/>
							<text fixtext="Utility Commission:"/>
							<template subtype="element" match="utilitybill">
								<children>
									<template subtype="element" match="uar">
										<children>
											<template subtype="element" match="utilitycommission">
												<children>
													<content/>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<newline/>
							<text fixtext="Written Inquiries: "/>
							<template subtype="element" match="utilitybill">
								<children>
									<template subtype="element" match="uar">
										<children>
											<template subtype="element" match="writteninquiries">
												<children>
													<content/>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<newline/>
							<text fixtext="Miss Utility: "/>
							<template subtype="element" match="utilitybill">
								<children>
									<template subtype="element" match="uar">
										<children>
											<template subtype="element" match="missutility">
												<children>
													<content/>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<newline/>
							<text fixtext="Service Outage: "/>
							<template subtype="element" match="utilitybill">
								<children>
									<template subtype="element" match="uar">
										<children>
											<template subtype="element" match="serviceoutage">
												<children>
													<content/>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<newline/>
							<newline/>
							<text fixtext="Unknown Addresses Found"/>
							<newline/>
							<tgrid>
								<properties border="1"/>
								<children>
									<tgridbody-cols>
										<children>
											<tgridcol/>
											<tgridcol/>
											<tgridcol/>
											<tgridcol/>
											<tgridcol/>
											<tgridcol/>
											<tgridcol/>
											<tgridcol/>
											<tgridcol/>
										</children>
									</tgridbody-cols>
									<tgridheader-rows>
										<children>
											<tgridrow>
												<children>
													<tgridcell>
														<children>
															<text fixtext="description"/>
														</children>
													</tgridcell>
													<tgridcell>
														<children>
															<text fixtext="addressee"/>
														</children>
													</tgridcell>
													<tgridcell>
														<children>
															<text fixtext="street"/>
														</children>
													</tgridcell>
													<tgridcell>
														<children>
															<text fixtext="city"/>
														</children>
													</tgridcell>
													<tgridcell>
														<children>
															<text fixtext="state"/>
														</children>
													</tgridcell>
													<tgridcell>
														<children>
															<text fixtext="country"/>
														</children>
													</tgridcell>
													<tgridcell>
														<children>
															<text fixtext="postalcode"/>
														</children>
													</tgridcell>
													<tgridcell>
														<children>
															<text fixtext="telephonenumber"/>
														</children>
													</tgridcell>
													<tgridcell>
														<children>
															<text fixtext="hours"/>
														</children>
													</tgridcell>
												</children>
											</tgridrow>
										</children>
									</tgridheader-rows>
									<tgridbody-rows>
										<children>
											<template subtype="element" match="utilitybill">
												<children>
													<template subtype="element" match="unknownaddress">
														<children>
															<tgridrow>
																<children>
																	<tgridcell>
																		<children>
																			<template subtype="attribute" match="description">
																				<children>
																					<content/>
																				</children>
																				<variables/>
																			</template>
																		</children>
																	</tgridcell>
																	<tgridcell>
																		<children>
																			<template subtype="element" match="addressee">
																				<children>
																					<content/>
																				</children>
																				<variables/>
																			</template>
																		</children>
																	</tgridcell>
																	<tgridcell>
																		<children>
																			<template subtype="element" match="street">
																				<children>
																					<content/>
																				</children>
																				<variables/>
																			</template>
																		</children>
																	</tgridcell>
																	<tgridcell>
																		<children>
																			<template subtype="element" match="city">
																				<children>
																					<content/>
																				</children>
																				<variables/>
																			</template>
																		</children>
																	</tgridcell>
																	<tgridcell>
																		<children>
																			<template subtype="element" match="state">
																				<children>
																					<content/>
																				</children>
																				<variables/>
																			</template>
																		</children>
																	</tgridcell>
																	<tgridcell>
																		<children>
																			<template subtype="element" match="country">
																				<children>
																					<content/>
																				</children>
																				<variables/>
																			</template>
																		</children>
																	</tgridcell>
																	<tgridcell>
																		<children>
																			<template subtype="element" match="postalcode">
																				<children>
																					<content/>
																				</children>
																				<variables/>
																			</template>
																		</children>
																	</tgridcell>
																	<tgridcell>
																		<children>
																			<template subtype="element" match="telephonenumber">
																				<children>
																					<content/>
																				</children>
																				<variables/>
																			</template>
																		</children>
																	</tgridcell>
																	<tgridcell>
																		<children>
																			<template subtype="element" match="hours">
																				<children>
																					<content/>
																				</children>
																				<variables/>
																			</template>
																		</children>
																	</tgridcell>
																</children>
															</tgridrow>
														</children>
														<variables/>
													</template>
												</children>
												<variables/>
											</template>
										</children>
									</tgridbody-rows>
								</children>
							</tgrid>
							<newline/>
							<newline/>
							<paragraph paragraphtag="h2">
								<children>
									<text fixtext="Summary"/>
								</children>
							</paragraph>
							<text fixtext="Issued: "/>
							<template subtype="element" match="utilitybill">
								<children>
									<template subtype="element" match="summary">
										<children>
											<template subtype="element" match="issuedate">
												<children>
													<content>
														<format datatype="date"/>
													</content>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<newline/>
							<text fixtext="Period From: "/>
							<template subtype="element" match="utilitybill">
								<children>
									<template subtype="element" match="summary">
										<children>
											<template subtype="element" match="billperiodbegin">
												<children>
													<content>
														<format datatype="date"/>
													</content>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<text fixtext="  To:  "/>
							<template subtype="element" match="utilitybill">
								<children>
									<template subtype="element" match="summary">
										<children>
											<template subtype="element" match="billperiodend">
												<children>
													<content>
														<format datatype="date"/>
													</content>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<newline/>
							<text fixtext="Prior Balance: "/>
							<template subtype="element" match="utilitybill">
								<children>
									<template subtype="element" match="summary">
										<children>
											<template subtype="element" match="priorbalance">
												<children>
													<content>
														<format datatype="decimal"/>
													</content>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<newline/>
							<text fixtext="Previous Payments"/>
							<newline/>
							<tgrid>
								<properties border="1"/>
								<children>
									<tgridbody-cols>
										<children>
											<tgridcol/>
											<tgridcol/>
											<tgridcol/>
										</children>
									</tgridbody-cols>
									<tgridheader-rows>
										<children>
											<tgridrow>
												<children>
													<tgridcell>
														<children>
															<text fixtext="date"/>
														</children>
													</tgridcell>
													<tgridcell>
														<children>
															<text fixtext="payee"/>
														</children>
													</tgridcell>
													<tgridcell>
														<children>
															<text fixtext="amount"/>
														</children>
													</tgridcell>
												</children>
											</tgridrow>
										</children>
									</tgridheader-rows>
									<tgridbody-rows>
										<children>
											<template subtype="element" match="utilitybill">
												<children>
													<template subtype="element" match="summary">
														<children>
															<template subtype="element" match="previouspayment">
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<children>
																					<template subtype="element" match="date">
																						<children>
																							<content>
																								<format datatype="date"/>
																							</content>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<template subtype="element" match="payee">
																						<children>
																							<content/>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<template subtype="element" match="amount">
																						<children>
																							<content>
																								<format datatype="decimal"/>
																							</content>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																</children>
																<variables/>
															</template>
														</children>
														<variables/>
													</template>
												</children>
												<variables/>
											</template>
										</children>
									</tgridbody-rows>
								</children>
							</tgrid>
							<text fixtext="Adjustments"/>
							<newline/>
							<tgrid>
								<properties border="1"/>
								<children>
									<tgridbody-cols>
										<children>
											<tgridcol/>
											<tgridcol/>
											<tgridcol/>
										</children>
									</tgridbody-cols>
									<tgridheader-rows>
										<children>
											<tgridrow>
												<children>
													<tgridcell>
														<children>
															<text fixtext="payee"/>
														</children>
													</tgridcell>
													<tgridcell>
														<children>
															<text fixtext="amount"/>
														</children>
													</tgridcell>
													<tgridcell>
														<children>
															<text fixtext="date"/>
														</children>
													</tgridcell>
												</children>
											</tgridrow>
										</children>
									</tgridheader-rows>
									<tgridbody-rows>
										<children>
											<template subtype="element" match="utilitybill">
												<children>
													<template subtype="element" match="summary">
														<children>
															<template subtype="element" match="adjustment">
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<children>
																					<template subtype="element" match="payee">
																						<children>
																							<content/>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<template subtype="element" match="amount">
																						<children>
																							<content>
																								<format datatype="decimal"/>
																							</content>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<template subtype="element" match="date">
																						<children>
																							<content>
																								<format datatype="date"/>
																							</content>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																</children>
																<variables/>
															</template>
														</children>
														<variables/>
													</template>
												</children>
												<variables/>
											</template>
										</children>
									</tgridbody-rows>
								</children>
							</tgrid>
							<text fixtext="Balance Forward: "/>
							<template subtype="element" match="utilitybill">
								<children>
									<template subtype="element" match="summary">
										<children>
											<template subtype="element" match="balanceforward">
												<children>
													<content>
														<format datatype="decimal"/>
													</content>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<newline/>
							<text fixtext="Current Charges: "/>
							<template subtype="element" match="utilitybill">
								<children>
									<template subtype="element" match="summary">
										<children>
											<template subtype="element" match="currentcharges">
												<children>
													<content>
														<format datatype="decimal"/>
													</content>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<newline/>
							<text fixtext="Total Due: "/>
							<template subtype="element" match="utilitybill">
								<children>
									<template subtype="element" match="summary">
										<children>
											<template subtype="element" match="totaldue">
												<children>
													<content>
														<format datatype="decimal"/>
													</content>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<newline/>
							<text fixtext="Due: "/>
							<template subtype="element" match="utilitybill">
								<children>
									<template subtype="element" match="summary">
										<children>
											<template subtype="element" match="duedate">
												<children>
													<content>
														<format datatype="date"/>
													</content>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<text fixtext="  Late Payment Penalty: "/>
							<template subtype="element" match="utilitybill">
								<children>
									<template subtype="element" match="summary">
										<children>
											<template subtype="element" match="latepayment">
												<children>
													<template subtype="element" match="penalty">
														<children>
															<content/>
														</children>
														<variables/>
													</template>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<text fixtext="Amount: "/>
							<template subtype="element" match="utilitybill">
								<children>
									<template subtype="element" match="summary">
										<children>
											<template subtype="element" match="latepayment">
												<children>
													<template subtype="element" match="amount">
														<children>
															<content/>
														</children>
														<variables/>
													</template>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<newline/>
							<newline/>
							<paragraph paragraphtag="h2">
								<children>
									<text fixtext="Charge Details"/>
								</children>
							</paragraph>
							<tgrid>
								<properties border="0" width="100%"/>
								<children>
									<tgridbody-cols>
										<children>
											<tgridcol/>
											<tgridcol/>
											<tgridcol/>
										</children>
									</tgridbody-cols>
									<tgridheader-rows>
										<children>
											<tgridrow>
												<children>
													<tgridcell>
														<children>
															<text fixtext="service"/>
														</children>
													</tgridcell>
													<tgridcell>
														<children>
															<text fixtext="rateschedule"/>
														</children>
													</tgridcell>
													<tgridcell>
														<children>
															<text fixtext="chargegroup"/>
														</children>
													</tgridcell>
												</children>
											</tgridrow>
										</children>
									</tgridheader-rows>
									<tgridbody-rows>
										<children>
											<template subtype="element" match="utilitybill">
												<children>
													<template subtype="element" match="details">
														<children>
															<tgridrow>
																<children>
																	<tgridcell>
																		<children>
																			<template subtype="attribute" match="service">
																				<children>
																					<content/>
																				</children>
																				<variables/>
																			</template>
																		</children>
																	</tgridcell>
																	<tgridcell>
																		<children>
																			<template subtype="element" match="rateschedule">
																				<children>
																					<content/>
																				</children>
																				<variables/>
																			</template>
																		</children>
																	</tgridcell>
																	<tgridcell>
																		<children>
																			<tgrid>
																				<properties border="0" width="100%"/>
																				<children>
																					<tgridbody-cols>
																						<children>
																							<tgridcol/>
																							<tgridcol/>
																							<tgridcol/>
																						</children>
																					</tgridbody-cols>
																					<tgridheader-rows>
																						<children>
																							<tgridrow>
																								<children>
																									<tgridcell>
																										<children>
																											<text fixtext="type"/>
																										</children>
																									</tgridcell>
																									<tgridcell>
																										<children>
																											<text fixtext="charges"/>
																										</children>
																									</tgridcell>
																									<tgridcell>
																										<children>
																											<text fixtext="subtotal"/>
																										</children>
																									</tgridcell>
																								</children>
																							</tgridrow>
																						</children>
																					</tgridheader-rows>
																					<tgridbody-rows>
																						<children>
																							<template subtype="element" match="chargegroup">
																								<children>
																									<tgridrow>
																										<children>
																											<tgridcell>
																												<children>
																													<template subtype="attribute" match="type">
																														<children>
																															<content/>
																														</children>
																														<variables/>
																													</template>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<children>
																													<tgrid>
																														<properties border="0" width="100%"/>
																														<children>
																															<tgridbody-cols>
																																<children>
																																	<tgridcol/>
																																	<tgridcol/>
																																	<tgridcol/>
																																	<tgridcol/>
																																</children>
																															</tgridbody-cols>
																															<tgridheader-rows>
																																<children>
																																	<tgridrow>
																																		<children>
																																			<tgridcell>
																																				<children>
																																					<text fixtext="description"/>
																																				</children>
																																			</tgridcell>
																																			<tgridcell>
																																				<children>
																																					<text fixtext="quantity"/>
																																				</children>
																																			</tgridcell>
																																			<tgridcell>
																																				<children>
																																					<text fixtext="rate"/>
																																				</children>
																																			</tgridcell>
																																			<tgridcell>
																																				<children>
																																					<text fixtext="total"/>
																																				</children>
																																			</tgridcell>
																																		</children>
																																	</tgridrow>
																																</children>
																															</tgridheader-rows>
																															<tgridbody-rows>
																																<children>
																																	<template subtype="element" match="charges">
																																		<children>
																																			<template subtype="element" match="charge">
																																				<children>
																																					<tgridrow>
																																						<children>
																																							<tgridcell>
																																								<children>
																																									<template subtype="element" match="description">
																																										<children>
																																											<content/>
																																										</children>
																																										<variables/>
																																									</template>
																																								</children>
																																							</tgridcell>
																																							<tgridcell>
																																								<children>
																																									<template subtype="element" match="quantity">
																																										<children>
																																											<content/>
																																										</children>
																																										<variables/>
																																									</template>
																																								</children>
																																							</tgridcell>
																																							<tgridcell>
																																								<children>
																																									<template subtype="element" match="rate">
																																										<children>
																																											<content/>
																																										</children>
																																										<variables/>
																																									</template>
																																								</children>
																																							</tgridcell>
																																							<tgridcell>
																																								<properties align="right"/>
																																								<children>
																																									<template subtype="element" match="total">
																																										<children>
																																											<content>
																																												<format datatype="decimal"/>
																																											</content>
																																										</children>
																																										<variables/>
																																									</template>
																																								</children>
																																							</tgridcell>
																																						</children>
																																					</tgridrow>
																																				</children>
																																				<variables/>
																																			</template>
																																		</children>
																																		<variables/>
																																	</template>
																																</children>
																															</tgridbody-rows>
																															<tgridfooter-rows>
																																<children>
																																	<tgridrow>
																																		<children>
																																			<tgridcell/>
																																			<tgridcell/>
																																			<tgridcell/>
																																			<tgridcell>
																																				<properties align="right"/>
																																				<children>
																																					<autocalc xpath="sum( charges/charge/total )"/>
																																				</children>
																																			</tgridcell>
																																		</children>
																																	</tgridrow>
																																</children>
																															</tgridfooter-rows>
																														</children>
																													</tgrid>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<properties align="right"/>
																												<children>
																													<template subtype="element" match="subtotal">
																														<children>
																															<content>
																																<format datatype="decimal"/>
																															</content>
																														</children>
																														<variables/>
																													</template>
																												</children>
																											</tgridcell>
																										</children>
																									</tgridrow>
																								</children>
																								<variables/>
																							</template>
																						</children>
																					</tgridbody-rows>
																					<tgridfooter-rows>
																						<children>
																							<tgridrow>
																								<children>
																									<tgridcell/>
																									<tgridcell>
																										<properties align="right"/>
																										<children>
																											<autocalc xpath="sum( chargegroup/charges/charge/total )"/>
																										</children>
																									</tgridcell>
																									<tgridcell>
																										<properties align="right"/>
																										<children>
																											<autocalc xpath="sum( chargegroup/subtotal )"/>
																										</children>
																									</tgridcell>
																								</children>
																							</tgridrow>
																						</children>
																					</tgridfooter-rows>
																				</children>
																			</tgrid>
																		</children>
																	</tgridcell>
																</children>
															</tgridrow>
														</children>
														<variables/>
													</template>
												</children>
												<variables/>
											</template>
										</children>
									</tgridbody-rows>
									<tgridfooter-rows>
										<children>
											<tgridrow>
												<children>
													<tgridcell/>
													<tgridcell/>
													<tgridcell>
														<properties align="right"/>
														<children>
															<template subtype="element" match="utilitybill">
																<children>
																	<template subtype="element" match="details">
																		<children>
																			<template subtype="element" match="total">
																				<children>
																					<content>
																						<format datatype="decimal"/>
																					</content>
																				</children>
																				<variables/>
																			</template>
																		</children>
																		<variables/>
																	</template>
																</children>
																<variables/>
															</template>
														</children>
													</tgridcell>
												</children>
											</tgridrow>
										</children>
									</tgridfooter-rows>
								</children>
							</tgrid>
							<newline/>
							<newline/>
							<newline/>
							<paragraph paragraphtag="h2">
								<children>
									<text fixtext="Billable Usage"/>
								</children>
							</paragraph>
							<text fixtext="Rate schedule: "/>
							<template subtype="element" match="utilitybill">
								<children>
									<template subtype="element" match="billableusage">
										<children>
											<template subtype="element" match="rateschedule">
												<children>
													<template subtype="element" match="name">
														<children>
															<content/>
														</children>
														<variables/>
													</template>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<newline/>
							<text fixtext="Rate in effect: "/>
							<template subtype="element" match="utilitybill">
								<children>
									<template subtype="element" match="billableusage">
										<children>
											<template subtype="element" match="rateschedule">
												<children>
													<template subtype="element" match="rateineffect">
														<children>
															<content/>
														</children>
														<variables/>
													</template>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
								<variables/>
							</template>
							<newline/>
							<newline/>
							<tgrid>
								<properties border="1"/>
								<children>
									<tgridbody-cols>
										<children>
											<tgridcol/>
											<tgridcol/>
										</children>
									</tgridbody-cols>
									<tgridheader-rows>
										<children>
											<tgridrow>
												<children>
													<tgridcell>
														<children>
															<text fixtext="description"/>
														</children>
													</tgridcell>
													<tgridcell>
														<children>
															<text fixtext="quantity"/>
														</children>
													</tgridcell>
												</children>
											</tgridrow>
										</children>
									</tgridheader-rows>
									<tgridbody-rows>
										<children>
											<template subtype="element" match="utilitybill">
												<children>
													<template subtype="element" match="billableusage">
														<children>
															<template subtype="element" match="usage">
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<children>
																					<template subtype="element" match="description">
																						<children>
																							<content/>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<template subtype="element" match="quantity">
																						<children>
																							<content/>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																</children>
																<variables/>
															</template>
														</children>
														<variables/>
													</template>
												</children>
												<variables/>
											</template>
										</children>
									</tgridbody-rows>
								</children>
							</tgrid>
							<newline/>
							<newline/>
							<paragraph paragraphtag="h2">
								<children>
									<text fixtext="Measured Usage"/>
								</children>
							</paragraph>
							<tgrid>
								<properties border="1"/>
								<children>
									<tgridbody-cols>
										<children>
											<tgridcol/>
											<tgridcol/>
											<tgridcol/>
											<tgridcol/>
											<tgridcol/>
											<tgridcol/>
										</children>
									</tgridbody-cols>
									<tgridheader-rows>
										<children>
											<tgridrow>
												<styles height="0.19in"/>
												<children>
													<tgridcell>
														<children>
															<text fixtext="estimated"/>
														</children>
													</tgridcell>
													<tgridcell>
														<children>
															<text fixtext="priorreaddate"/>
														</children>
													</tgridcell>
													<tgridcell>
														<children>
															<text fixtext="presentreaddate"/>
														</children>
													</tgridcell>
													<tgridcell>
														<children>
															<text fixtext="nextreaddate"/>
														</children>
													</tgridcell>
													<tgridcell>
														<children>
															<text fixtext="identifier"/>
														</children>
													</tgridcell>
													<tgridcell/>
												</children>
											</tgridrow>
										</children>
									</tgridheader-rows>
									<tgridbody-rows>
										<children>
											<template subtype="element" match="utilitybill">
												<children>
													<template subtype="element" match="measuredusage">
														<children>
															<template subtype="element" match="meter">
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<children>
																					<template subtype="element" match="estimated">
																						<children>
																							<content/>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<template subtype="element" match="priorreaddate">
																						<children>
																							<content>
																								<format datatype="date"/>
																							</content>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<template subtype="element" match="presentreaddate">
																						<children>
																							<content>
																								<format datatype="date"/>
																							</content>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<template subtype="element" match="nextreaddate">
																						<children>
																							<content>
																								<format datatype="date"/>
																							</content>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<template subtype="element" match="identifier">
																						<children>
																							<content/>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<tgrid>
																						<properties border="1"/>
																						<children>
																							<tgridbody-cols>
																								<children>
																									<tgridcol/>
																									<tgridcol/>
																									<tgridcol/>
																									<tgridcol/>
																									<tgridcol/>
																									<tgridcol/>
																									<tgridcol/>
																								</children>
																							</tgridbody-cols>
																							<tgridheader-rows>
																								<children>
																									<tgridrow>
																										<children>
																											<tgridcell>
																												<children>
																													<text fixtext="identifier"/>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<children>
																													<text fixtext="description"/>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<children>
																													<text fixtext="units"/>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<children>
																													<text fixtext="priorreading"/>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<children>
																													<text fixtext="presentreading"/>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<children>
																													<text fixtext="factor"/>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<children>
																													<text fixtext="total"/>
																												</children>
																											</tgridcell>
																										</children>
																									</tgridrow>
																								</children>
																							</tgridheader-rows>
																							<tgridbody-rows>
																								<children>
																									<template subtype="element" match="register">
																										<children>
																											<tgridrow>
																												<children>
																													<tgridcell>
																														<children>
																															<template subtype="element" match="identifier">
																																<children>
																																	<content/>
																																</children>
																																<variables/>
																															</template>
																														</children>
																													</tgridcell>
																													<tgridcell>
																														<children>
																															<template subtype="element" match="description">
																																<children>
																																	<content/>
																																</children>
																																<variables/>
																															</template>
																														</children>
																													</tgridcell>
																													<tgridcell>
																														<children>
																															<template subtype="element" match="units">
																																<children>
																																	<content/>
																																</children>
																																<variables/>
																															</template>
																														</children>
																													</tgridcell>
																													<tgridcell>
																														<children>
																															<template subtype="element" match="priorreading">
																																<children>
																																	<content>
																																		<format datatype="decimal"/>
																																	</content>
																																</children>
																																<variables/>
																															</template>
																														</children>
																													</tgridcell>
																													<tgridcell>
																														<children>
																															<template subtype="element" match="presentreading">
																																<children>
																																	<content>
																																		<format datatype="decimal"/>
																																	</content>
																																</children>
																																<variables/>
																															</template>
																														</children>
																													</tgridcell>
																													<tgridcell>
																														<children>
																															<template subtype="element" match="factor">
																																<children>
																																	<content>
																																		<format datatype="integer"/>
																																	</content>
																																</children>
																																<variables/>
																															</template>
																														</children>
																													</tgridcell>
																													<tgridcell>
																														<children>
																															<template subtype="element" match="total">
																																<children>
																																	<content>
																																		<format datatype="decimal"/>
																																	</content>
																																</children>
																																<variables/>
																															</template>
																														</children>
																													</tgridcell>
																												</children>
																											</tgridrow>
																										</children>
																										<variables/>
																									</template>
																								</children>
																							</tgridbody-rows>
																						</children>
																					</tgrid>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																</children>
																<variables/>
															</template>
														</children>
														<variables/>
													</template>
												</children>
												<variables/>
											</template>
										</children>
									</tgridbody-rows>
								</children>
							</tgrid>
							<newline/>
							<paragraph paragraphtag="h2">
								<children>
									<text fixtext="Usage History"/>
								</children>
							</paragraph>
							<tgrid>
								<properties border="1"/>
								<children>
									<tgridbody-cols>
										<children>
											<tgridcol/>
											<tgridcol/>
											<tgridcol/>
											<tgridcol/>
										</children>
									</tgridbody-cols>
									<tgridheader-rows>
										<children>
											<tgridrow>
												<children>
													<tgridcell>
														<children>
															<text fixtext="date"/>
														</children>
													</tgridcell>
													<tgridcell>
														<children>
															<text fixtext="days"/>
														</children>
													</tgridcell>
													<tgridcell>
														<children>
															<text fixtext="register"/>
														</children>
													</tgridcell>
													<tgridcell>
														<children>
															<text fixtext="total"/>
														</children>
													</tgridcell>
												</children>
											</tgridrow>
										</children>
									</tgridheader-rows>
									<tgridbody-rows>
										<children>
											<template subtype="element" match="utilitybill">
												<children>
													<template subtype="element" match="usagehistory">
														<children>
															<template subtype="element" match="usage">
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<children>
																					<template subtype="element" match="date">
																						<children>
																							<content>
																								<format datatype="date"/>
																							</content>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<template subtype="element" match="days">
																						<children>
																							<content>
																								<format datatype="integer"/>
																							</content>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<template subtype="element" match="register">
																						<children>
																							<tgrid>
																								<properties border="1"/>
																								<children>
																									<tgridbody-cols>
																										<children>
																											<tgridcol/>
																											<tgridcol/>
																										</children>
																									</tgridbody-cols>
																									<tgridheader-rows>
																										<children>
																											<tgridrow>
																												<children>
																													<tgridcell>
																														<children>
																															<text fixtext="identifier"/>
																														</children>
																													</tgridcell>
																													<tgridcell>
																														<children>
																															<text fixtext="total"/>
																														</children>
																													</tgridcell>
																												</children>
																											</tgridrow>
																										</children>
																									</tgridheader-rows>
																									<tgridbody-rows>
																										<children>
																											<tgridrow>
																												<children>
																													<tgridcell>
																														<children>
																															<template subtype="element" match="identifier">
																																<children>
																																	<content/>
																																</children>
																																<variables/>
																															</template>
																														</children>
																													</tgridcell>
																													<tgridcell>
																														<children>
																															<template subtype="element" match="total">
																																<children>
																																	<content/>
																																</children>
																																<variables/>
																															</template>
																														</children>
																													</tgridcell>
																												</children>
																											</tgridrow>
																										</children>
																									</tgridbody-rows>
																								</children>
																							</tgrid>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<template subtype="element" match="total">
																						<children>
																							<content/>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																</children>
																<variables/>
															</template>
														</children>
														<variables/>
													</template>
												</children>
												<variables/>
											</template>
										</children>
									</tgridbody-rows>
								</children>
							</tgrid>
							<newline/>
							<newline/>
							<newline/>
							<newline/>
							<newline/>
						</children>
						<variables/>
					</template>
				</children>
			</globaltemplate>
		</children>
	</mainparts>
	<globalparts/>
	<pagelayout>
		<properties paperheight="11.69in" paperwidth="8.27in"/>
	</pagelayout>
	<designfragments/>
</structure>
