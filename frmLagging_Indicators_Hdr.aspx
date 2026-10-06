<%@ Page Language="C#" AutoEventWireup="true" CodeFile="frmLagging_Indicators_Hdr.aspx.cs"
    Inherits="Quality_And_Safety_frmLagging_Indicators_Hdr" %>

<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head id="Head1" runat="server">
    <title>Lagging Indicators Information</title>
   <link href="../StyleSheet.css" type="text/css" rel="stylesheet" />
    <script type="text/javascript" language="javascript" src="../Javascript/generic.js"> </script> 
    <script type="text/javascript" language="javascript" src="../Javascript/Open_Search.js"> </script>
    <script type="text/javascript" language="javascript" src="../Javascript/Open_ErrorWin.js"> </script>   
    <script type="text/javascript" language="javascript" src="../JavaScript/jquery.min.js"></script>
    <script type="text/javascript" language="javascript" src="../JavaScript/bootstrap.min.js"></script>
    <script type="text/javascript" language="javascript" src="../JavaScript/CommonModal.js"></script>
    
    <link href="../BootstrapStyleSheet.min.css" type="text/css" rel="stylesheet" />  

    <script type="text/javascript">

        window.onload = function() { }
        function validate(strFlag) {

            var msg = "";
            var strServerDt = '<%= Session["ServerDt"].ToString() %>';

            var strToDt = "";

            /// Set a value to indicate the control/event that causes a postback.
            SetPostbackFlag(strFlag);
            
 
            if (strFlag == "ADD") 
            {
                if (document.getElementById('<%=tbLagging_Indicator_Id_Hidden.ClientID%>').value != "") 
                {
                   
                       ShowMessage(400, 75, 'You are currently in update mode, New record will not be added in this mode.');
                       return false;
                      
                }
                if (document.getElementById('<%=tbCompany_Id_Hidden.ClientID%>').value == "") {
                    document.getElementById('<%=tbCompany_Name.ClientID%>').focus();
                    msg += "- Company must be selected<br><br>";
                }

                if (document.getElementById('<%=tbRig_Id_Hidden.ClientID%>').value == "") {
                    document.getElementById('<%=tbRig.ClientID%>').focus();
                    msg += "- Rig must be selected <br><br>";
                }
                if (document.getElementById('<%=tbReport_No.ClientID%>').value == "") {
                    document.getElementById('<%=tbReport_No.ClientID%>').focus();
                    msg += "- Report No. must be entered <br><br>";
                }
                 if (document.getElementById('<%=tbPeriod.ClientID%>').value == "") {
                    document.getElementById('<%=tbPeriod.ClientID%>').focus();
                    msg += "- Period must be entered <br><br>";
                }   
                
                else
                {  
                
                        var tbPeriod = '01/'+ document.getElementById('<%=tbPeriod.ClientID%>').value ;

                        if (compareDates(strServerDt, 'dd/MM/yyyy', tbPeriod, 'dd/MM/yyyy') == 1){}
                                 
                        else
                        {
                            msg += "- Period must be less than current date<br><br>";
                            document.getElementById('<%=tbPeriod.ClientID%>').focus();
                        }                         
                  
                }                      
 

            }
            else  //Update 
            {

                /// Blocking ADD button when an existing record is selected.
                if (document.getElementById('<%=tbLagging_Indicator_Id_Hidden.ClientID%>').value == "") {
                    ShowMessage(400, 75, 'Select record to Update.');
                    return false;
                }
                else
                {
                    if(document.getElementById('<%=grdLagging_Indicators.ClientID%>')!=null)
                    {
                           msg+=Check_Lagging_Indicators_Dtl();
                    }                              
                }             
            }



            if (msg == "") {
                return true;
            }
            else {
                ShowErrorWin1(msg);
                return false;
            }

        }
        function Validate_Numeric(obj)
        {
           var valid_input = isCharValid(obj.value, 'N');
           var strText = obj.value;
           var len = strText.length;

           if (!valid_input)
           {
                obj.value = obj.value.substr(0, len-1);
                return;
           }
        }
        function Show_Main_Data() {
            SetPostbackFlag("SEARCH");
            Open_Search_Window('LAGGING_INDICATORS_HDR', document.forms[0].name, 'tbLagging_Indicator_Id_Hidden', 'tbCompany_Name', '', '%', 'Y', 'Y', 'N');
            return;
        }

        function Show_Rig() 
        {
            SetPostbackFlag("RIG");            
            Open_Search_Window('RIG', document.forms[0].name, 'tbRig_Id_Hidden', 'tbRig', '', '%', 'N', 'Y', 'N');
            return;
        }

        function Show_Company() 
        {
            SetPostbackFlag("COMPANY");
            ///Display all the active companies which belongs to the Business_Grp_Id = 2 
            var strFilterString =  " Business_Grp_Id = 2 ";
            Open_Search_Window('COMPANY', document.forms[0].name, 'tbCompany_Id_Hidden', 'tbCompany_Name', strFilterString, '%', 'N', 'Y', 'N');
            return;
        }
        
        ///This function is to keep track of Which record user have changed  and Update only that records 
        //
        function Data_Change(ObjData_Change,strType,Obj_CheckDate)
        {            
              if(strType =="Y")//Check for 
              {
                 var res = checkNum(Obj_CheckDate ,3,0);
                 if(res == false)
                 {
                    return ;
                 }
                 else
                 {
                    ObjData_Change.value ="Y";
                 }  
              }
              else
              {
                   ObjData_Change.value ="Y";
              }        
        }
        
        
        function Check_Lagging_Indicators_Dtl() {
 
            var msg;
            msg = "";
                   
            var DgHelpData = document.getElementById('<%=grdLagging_Indicators.ClientID%>');
            var rCount = DgHelpData.rows.length;
            var rowIdx;
                     

             for (rowIdx = 1; rowIdx < rCount   ; rowIdx++)
             {
                  var rowElement = DgHelpData.rows[rowIdx];
                  var tbLagging_Indicator_Dtl_Id_Hidden = rowElement.cells[0].firstChild;
                  
                  var tbData_Change_Id_Hidden = rowElement.cells[6].firstChild;
                  
                  if (tbData_Change_Id_Hidden.value == "Y") {
                      var tbTotal_Count = rowElement.cells[4].firstChild;
                      var tbActive = rowElement.cells[5].firstChild;

                      if (tbTotal_Count.value != "") {
                          if (!isCharValid(tbTotal_Count.value, 'N')) {
                              tbTotal_Count.focus();
                              msg += "- Total count must be numeric only<br><br>&nbsp;&nbsp;(Work Grp : " + rowElement.cells[1].innerHTML + " - " + rowElement.cells[2].innerHTML + " ).<br><br>";
                          }
                      }


                      if (tbActive.value == "") {
                          msg += "- Active must be entered <br><br>&nbsp;&nbsp;(Work Grp : " + rowElement.cells[1].innerHTML + " - " + rowElement.cells[2].innerHTML + " ).<br><br>";
                      }
                  }
                    if(msg!="")
                    {
                     return  msg;
                    }
                }
 
                      
            return msg;

            

        }
        function CheckY_N(obj)
        {       
            obj.value = obj.value.toUpperCase();            

            if ( ( obj.value != 'Y') &&
                 ( obj.value != 'N')  
            )
            {                
                obj.value = "";
            }
        }

        /// Determine whether page has to be posted back by passing a flag to a hidden textbox.
        function SetPostbackFlag(strFlag) 
        {
            document.getElementById('<%=tbPostbackFlag_Hidden.ClientID%>').value = strFlag;
            return true;
        }  
        
    </script>

</head>
<body class="body" onkeydown="if (event.keyCode==13) {event.keyCode=9; return event.keyCode }">
    <form id="frmLagging_Indicators_Hdr" runat="server">
    <div style="left: 0px; width: 100%; position: absolute; top: 0px; height: 88%">
        <table style="width: 100%" class="table_header">
            <tr>
                
                <td class="td_button">
                    <asp:Button ID="btnSearch" runat="server" Text="Search" Width="100%" OnClientClick="Show_Main_Data();return false;"
                        CssClass="td_button" />
                </td>
                <td class="td_button">
                    <asp:Button ID="btnAdd" runat="server" Text="Add" Width="100%" OnClick="btnAdd_Click"
                        OnClientClick="return validate('ADD');" CssClass="td_button" />
                </td>
                <td class="td_button">
                    <asp:Button ID="btnUpdate" runat="server" Text="Update" Width="100%" CssClass="td_button"
                        OnClientClick="return validate('UPDATE');" OnClick="btnUpdate_Click" />
                </td>
                <td class="td_button">
                    <asp:Button ID="btnClear" runat="server" Text="Clear" Width="100%" CssClass="td_button"
                        OnClientClick="SetPostbackFlag('CLEAR');" OnClick="btnClear_Click" />
                </td>                
                <td class="td_button">
                    &nbsp;
                </td>
                <td class="td_header" style="width: 40%">
                    HSE - Lagging Indicators
                </td>
            </tr>
        </table>
        <br />
        <table cellpadding="0" cellspacing="0" class="table">
            <tr>
                <td style="width: 15%;">
                </td>
                <td style="width: 10%">
                </td>
                <td style="width: 8%">
                </td>
                <td style="width: 5%">
                </td>
                <td style="width: 3%">
                </td>
                <td style="width: 10%">
                </td>
                <td style="width: 5%">
                </td>
                <td style="width: 10%">
                </td>
                <td>
                </td>
            </tr>
            <tr>
                <td class="td_caption">
                    <span class="star">*</span>&nbsp;Company
                </td>
                <td class="td">
                    <asp:TextBox ID="tbCompany_Name" runat="server" CssClass="textbox_readonly" MaxLength="1"
                        Text="OGD Services Limited" Width="210px" Height="15px" onKeyDown="return RejectInput();"></asp:TextBox>&nbsp;<asp:ImageButton
                            ID="ibtnCompany" runat="server" OnClientClick="Show_Company();return false;"
                            ImageAlign="Middle" ImageUrl="~/Images/Icons/search.gif" ToolTip="Find Company"
                            CssClass="image_search" />
                </td>
                <td class="td_caption">
                    <span class="star">*</span>&nbsp;Rig
                </td>
                <td class="td" colspan="2">
                    <asp:TextBox ID="tbRig" runat="server" CssClass="textbox_readonly" MaxLength="1"
                        Width="105px" OnKeyDown="return RejectInput();"></asp:TextBox>&nbsp;<asp:ImageButton
                            ID="ibtnRig_Id" runat="server" OnClientClick="Show_Rig();return false;" ImageAlign="Middle"
                            ImageUrl="~/Images/Icons/search.gif" ToolTip="Find Rig" CssClass="image_search" />
                </td>
                <td class="td_caption">
                    <span class="star">*</span>&nbsp;Report No
                </td>
                <td class="td">
                    <asp:TextBox ID="tbReport_No" runat="server" CssClass="textbox" MaxLength="12" Width="70px"
                        Height="15px"></asp:TextBox>
                </td>
                <td class="td_caption">
                    <span class="star">*</span>&nbsp;Period
                </td>
                <td class="td">
                    <asp:TextBox ID="tbPeriod" runat="server" CssClass="textbox" MaxLength="7" onBlur="return CheckDate_MthYr_OnBlur(this);"
                        onkeyup="return DateMask_MthYr(this);" Width="50px"></asp:TextBox>&nbsp;(mm/yyyy)
                </td>
            </tr>
        </table>
        <br />
        <% if (tbLagging_Indicator_Id_Hidden.Value != "")
           { %>
        <table cellpadding="0" cellspacing="0" class="table_section">
            <tr>
                <td class="td_section">
                    Lagging Indicators Detail
                </td>
                <td>
                    &nbsp;
                </td>
            </tr>
        </table>
        <div id="divHelpData" class="div_gridview" style="  height: 430px">
            <asp:GridView ID="grdLagging_Indicators" runat="server" AutoGenerateColumns="false"
                CssClass="GridView" ShowHeader="true" Width="95%" OnRowDataBound="grdLagging_Indicators_RowDataBound">
                <Columns>
                    <asp:TemplateField HeaderText="tbLagging_Indicator_Dtl_Id_Hidden" Visible="true"
                        HeaderStyle-CssClass="hiddencol" FooterStyle-CssClass="hiddencol" ItemStyle-CssClass="hiddencol">
                        <ItemTemplate>
                            <input id="tbLagging_Indicator_Dtl_Id_Hidden" runat="server" name="tbLagging_Indicator_Dtl_Id_Hidden"
                                visible="true" style="z-index: 104; left: 43px; width: 0px; position: absolute;
                                top: 258px; height: 24px" type="hidden" value='<%# Bind("Lagging_Indicator_Dtl_Id") %>' />
                        </ItemTemplate>
                        <FooterStyle CssClass="hiddencol"></FooterStyle>
                        <HeaderStyle CssClass="hiddencol"></HeaderStyle>
                        <ItemStyle CssClass="hiddencol"></ItemStyle>
                    </asp:TemplateField>
                    <asp:BoundField DataField="Workgroup" HeaderText="Work Group">
                        <ItemStyle Width="126px" HorizontalAlign="Center" />
                        <HeaderStyle HorizontalAlign="Center"></HeaderStyle>
                    </asp:BoundField>
                    <asp:BoundField DataField="Indicator_Type_Name" HeaderText="Indicator Type">
                        <ItemStyle Width="274" HorizontalAlign="Left" />
                    </asp:BoundField>
                    <asp:BoundField DataField="Indicator_Subtype_Name" HeaderText="Indicator Subtype">
                        <ItemStyle Width="274px" HorizontalAlign="Left" />
                    </asp:BoundField>                   
                    <asp:TemplateField HeaderText="Total Duration" SortExpression="Total_Duration">
                        <ItemTemplate>
                            <asp:TextBox ID="tbTotal_Count" runat="server" CssClass="textbox_right" Text='<%# Bind("Total_Count") %>'
                                onKeyUp="Validate_Numeric(this);"    onblur="return checkNum(this,10,0);" MaxLength="10" Width="45px" Height="16px"></asp:TextBox>
                        </ItemTemplate>
                        <HeaderStyle HorizontalAlign="Center" />
                        <ItemStyle HorizontalAlign="Center" />
                    </asp:TemplateField>                    
                    <asp:TemplateField HeaderText="Active" SortExpression="Active">
                        <ItemTemplate>
                            <asp:TextBox ID="tbActive" runat="server" Text='<%# Bind("Active") %>' CssClass="textbox_center"
                                MaxLength="1" Width="16px" onKeyUp="CheckY_N(this);"></asp:TextBox>
                        </ItemTemplate>
                        <HeaderStyle HorizontalAlign="Center" />
                        <ItemStyle HorizontalAlign="Center" />
                    </asp:TemplateField>
                    <asp:TemplateField HeaderText="tbData_Change_Id_Hidden" Visible="true" HeaderStyle-CssClass="hiddencol"
                        FooterStyle-CssClass="hiddencol" ItemStyle-CssClass="hiddencol">
                        <ItemTemplate>
                            <input id="tbData_Change_Id_Hidden" runat="server" name="tbData_Change_Id_Hidden"
                                visible="true" style="z-index: 104; left: 43px; width: 0px; position: absolute;
                                top: 258px; height: 24px" type="hidden" value='<%# Bind("Data_Change") %>' />
                        </ItemTemplate>
                        <FooterStyle CssClass="hiddencol"></FooterStyle>
                        <HeaderStyle CssClass="hiddencol"></HeaderStyle>
                        <ItemStyle CssClass="hiddencol"></ItemStyle>
                    </asp:TemplateField>
                </Columns>
                <RowStyle CssClass="GridView_RowStyle" />
                <HeaderStyle  CssClass="GridView_HeaderStyle" Height="20px" />
                <AlternatingRowStyle CssClass="GridView_AlternatingRowStyle" />
                <SelectedRowStyle CssClass="GridView_FooterStyle" />
                <FooterStyle CssClass="GridView_FooterStyle" />
            </asp:GridView>
        </div>
        <% } %>
        <!--Header -->
        <input id="tbLagging_Indicator_Id_Hidden" runat="server" name="tbLagging_Indicator_Id_Hidden"
            style="z-index: 104; left: 71px; width: 24px; position: absolute; top: 408px;
            height: 24px" type="hidden" />
        <input id="tbCompany_Id_Hidden" runat="server" name="tbCompany_Id_Hidden" style="z-index: 104;
            left: 71px; width: 24px; position: absolute; top: 408px; height: 24px" type="hidden"
            value="10" />
        <input id="tbRig_Id_Hidden" runat="server" name="tbRig_Id_Hidden" style="z-index: 104;
            left: 102px; width: 24px; position: absolute; top: 257px; height: 24px" type="hidden" />
        <input id="tbPostbackFlag_Hidden" runat="server" name="tbPostbackFlag_Hidden" style="z-index: 104;
            left: 189px; width: 24px; position: absolute; top: 307px; height: 24px" type="hidden" />
    </div>
    </form>
</body>
</html>
